# Mellum Worker and Mellum Mode: Mellum 2.1 as a coding worker under Pi

**Status: shipped 2026-10-09; two ways to use the worker (§4 delegated, §4b in-session), both measured. Follow-ups are scheduled in [2026-10-09-future-work.md](research/2026-10-09-future-work.md). Every number links to its record under `docs/research/ladder/`; the lean-down that produced the shipped worker is summarised in [ablation-summary.md](research/ladder/ablation-summary.md).**

This is the practical recipe that came out of the research in
[docs/research/](research/): run the local Mellum 2.1 model not as the agent
you talk to, but as a narrowly configured *child* that your normal Pi session
hands bounded coding tasks to. Everything here was measured with the prompt
ladder in `ladder/`; the numbers link to their records.

## 1. What this is, and is not

Mellum 2.1 Thinking (12B MoE, 2.5B active, Q6 MLX conversion) could not run
the Superpowers workflow as the primary agent: it dispatched skill names as
agents, retried after errors, and ended turns without answering
([recovery report](research/mellum-recovery-2026-10-07/report.md)). The same
model, given a clean prompt and file tools only, completes bounded tasks.

So the recipe inverts the roles. Your usual model (DeepSeek Flash here) stays
the parent with Superpowers and pi-subagents; Mellum is `mellum-worker`, a
child with `read, grep, find, ls, bash, edit, write`, no skills catalog, no
bootstrap, no delegation, and a prompt made of facts about the test
command.

What it is good for, measured: one-line fixes, adding a function with its
test, a rename across two files, and three-file changes with a named failing
test. What it is not: exploration, design, or scoping a task from a symptom
on its own (see the ladder results below).

## 2. Inference server (oMLX)

Serve `Mellum2.1-12B-A2.5B-Thinking-6bit` on oMLX 0.6.4 as in the main
[README](../README.md). The converted model is published at
<https://huggingface.co/pauleveritt/Mellum2.1-12B-A2.5B-Thinking-mlx-6bit>
(9.9 GB, two safetensors shards, MLX 6-bit), so it can be pulled with
`hf download pauleveritt/Mellum2.1-12B-A2.5B-Thinking-mlx-6bit` instead of
converted. Settings: 56,000-token context window, native hybrid cache,
cache quantization off, one concurrent request.

**Which settings actually apply.** oMLX gives a request's sampling and cap
values precedence over the per-model profile. Pi sends `max_tokens`,
`temperature`, `top_p`, `top_k`, `min_p`, `seed`, and `presence_penalty` on
every request from its `models.json` entry. So:

| setting | where it is decided | value used |
| --- | --- | --- |
| `max_tokens` | Pi `models.json` → `maxTokens` | 16,384 (model-card per-turn budget); a 4,096 cap cut off one three-file run mid-thought ([phases 1c/1d](research/ladder/phase1d-tuned-effective/README.md)) |
| temperature / top_p / top_k | Pi `models.json` → `samplingParams`, else Pi defaults | Pi default is 1 / 0.95 / 20 (the model card's agentic sampling) |
| presence / repetition penalty | request | 0 / 1.0 — 0.5 showed nothing measurable (1c vs 1d: 13/15 vs 14/15, same request and error counts), though that comparison changed the cap at the same time |
| thinking budget | server profile only | off — a 4,096-per-block budget was never triggered in 15 runs; the request cap is what binds |
| `max_tool_result_tokens` | server profile only | off — the largest tool result in 30 runs was 2,639 characters |
| `forced_ct_kwargs: ["enable_thinking"]` | server profile only | on — a client cannot switch thinking off |
| thinking level (`thinking:` in the agent file, `--thinking`) | nowhere | inert: Pi's level does not reach an `openai-completions` provider; two runs at "high" and "medium" sent byte-identical requests ([ablation A5](research/ladder/ablation-a5-thinking-medium/README.md)) |
| `thinking_budget` (request field) | a hook could send it (`ladder/thinking-budget.js`) | not enforced for this model: oMLX needs a reasoning parser configured to build its budget processor ([A13](research/ladder/ablation-a13-budget-medium/README.md)) |

Verify with one request through the proxy or Pi's `before_provider_request`
hook (`ladder/record-pi.js`) that the values you expect are the values sent;
the ladder records them per run as `effective_params`.

The oMLX admin API is at `/admin/api/models/<id>/settings` (no auth when
`skip_api_key_verification` is on). `ladder/omlx_profiles.py` switches
profiles with a snapshot and a verified restore.

## 3. Pi setup

Project-local; the only change outside the project is the `models.json` entry at the end of this list:

- `.pi/agents/mellum-worker.md` — the worker. Each frontmatter line removes
  something: `systemPromptMode: replace` (no Pi base prompt),
  `inheritProjectContext/GlobalContext/Skills: false` (no AGENTS.md, no skills
  catalog), `extensions:` empty (no Superpowers in the child; pi-subagents warns
  about this on every launch — intended), `tools:` the seven file tools, and
  `excludeTools: contact_supervisor` (pi-subagents injects that tool and a
  supervisor-protocol prompt block into every child unless excluded; the
  supervisor protocol is what Mellum failed, measured in
  [ablation A8](research/ladder/ablation-a8-delegated-lean/README.md)), and
  `acceptance: level none` (the parent verifies by running the tests; an
  acceptance contract competed with the reply format and recorded a correct
  run as rejected). Nothing else: no `thinking:` (the level never reaches
  oMLX), no `allowedAgents:` (the child has no `subagent` tool to narrow),
  no `defaultContext:` (pi-subagents' default is `fresh`).
- `prompts/mellum-worker.md` (v5, 643 characters) — the body, duplicated
  into the agent file; a test keeps them identical. One line of role, six
  facts about the test command, one line for when the files cannot be found.
  *The task is complete only when the test command exits 0* and *if it
  fails, read the failure, change the code, and run it again* took rung 5
  from 0/3 to 3/3 ([phase 0b](research/ladder/phase0b-baseline-v3/README.md)).
  v3's six-step procedure and five tool descriptions were measured and
  removed ([A2](research/ladder/ablation-a2-v4a/README.md), [A3](research/ladder/ablation-a3-v4b/README.md));
  the missing-files line stays because the run without it edited a test
  ([A4](research/ladder/ablation-a4-v4c/README.md)).
- `.pi/mellum/mellum-guards.ts` — the child's guards, loaded only through the
  agent file's `subagentOnlyExtensions`. It lives outside `.pi/extensions/`
  on purpose: Pi auto-loads that directory into every session in a trusted
  project, parent included. On by default: the empty-final nudge (cap 3)
  and the loop breaker (five unbroken repeats of one call, forgotten after
  any edit, write, or bash call). Dormant: new-file-only `write`, step
  budget. See §6.
- No parent-side skill. One existed; it was read in 2 of 15 runs and the
  pass rate was 15/15 with or without it ([phase 3b](research/ladder/phase3b-delegated-skill/README.md)),
  so it was removed. Its content is §4's one paragraph on briefing.
- Optional, global to your profile: `{"intercomBridge": {"mode": "off"}}`
  in `~/.pi/agent/extensions/subagent/config.json` removes the 1,582-character
  supervisor block pi-subagents puts in every child's prompt; the worker
  passed 15/15 with it off and its prompt halved
  ([A11](research/ladder/ablation-a11-delegated-nointercom/README.md)).
  Every other subagent of yours loses `contact_supervisor` too, so only if
  none of them needs it.
- `~/.pi/agent/models.json` omlx entry must set `supportsDeveloperRole: false`:
  Pi otherwise sends the instructions as a `developer` message for a
  reasoning model on a localhost provider, and the mode replaces either
  role but older versions of the filter did not. Also `contextWindow 56000`, `maxTokens
  16384`, `thinkingFormat: qwen-chat-template`.

Try it safely:

```bash
uv run python -m ladder.sandbox 1   # prints a disposable copy of rung 1 with .pi/ included
```

then `cd` there, start `pi`, and say *Use mellum-worker to do this: the cart
total ignores quantity, fix it*. Never run the worker inside `fixtures/`
itself; it edits in place.

## 4. Using Mellum Worker (delegated)

In a normal Pi session, name the worker: "Use mellum-worker to do this: …".
Your parent scopes the task, writes the brief, launches the child, and — in
every measured run — runs the tests itself before reporting. The child's
one recorded pathology is a turn that ends with `stop` and no text;
pi-subagents reports it as "Subagent produced no output". In sixty
delegated runs the parent re-dispatched on that error and the run then
passed ten times out of eleven; the one miss was reported as blocked, never
as done ([A9](research/ladder/ablation-a9-delegated-final/README.md)).

The ladder's five sentences, as a user would type them, and what happened:

| rung | sentence | worker alone, prompt v3 (direct, greedy; cap 4,096 / cap 16,384) | via your Pi (delegated, prompt v3) |
| --- | --- | --- | --- |
| 1 | the cart total ignores quantity, fix it | 3/3 / 3/3 | 3/3 |
| 2 | add a balance() that sums the entries, with a test | 3/3 / 3/3 | 3/3 |
| 3 | rename fetch_rows to load_rows everywhere | 3/3 / 3/3 | 3/3 |
| 4 | make the failing test pass (three failing tests, three files) | 2/3 / 2/3 | 3/3 |
| 5 | the export is missing the totals row (same, plus a decoy, no test named) | 2/3 / 3/3 | 3/3 |

The worker as it ships, prompt v5, delegated: 3/3 on every rung, no
re-dispatch, no empty child turn ([A10](research/ladder/ablation-a10-delegated-v5/README.md)).

Mellum as the *primary* agent in your own profile, given the same sentences
([phase 0c](research/ladder/phase0c-primary-operator/README.md)): 3/3, 2/3,
3/3, 2/3, 0/3. It reads and follows the Superpowers skills; it fails when a
skill asks a question nobody answers, when a turn ends empty, and on the
three-file change by symptom. Bare Pi with no extensions or skills
([phase 0c plain](research/ladder/phase0c-primary-plain/README.md)): 3/3, 3/3,
2/3, 0/3, 0/3, with four empty finals, three false "fixed" claims, and one
rewritten test file. The worker alone, same model and harness but greedy
decoding and the worker prompt, is 15/15
([phase 2b](research/ladder/phase2b-guards-bounded/README.md), [A2](research/ladder/ablation-a2-v4a/README.md),
[A3](research/ladder/ablation-a3-v4b/README.md)); only the delegated runs
measure it at the sampling your Pi actually uses.

Where it stops working: rung 5 is a three-file change described only by a
symptom. Alone, the worker's failures there are honest ("tests still
failing") or silent (empty final). With a parent that scopes first, it
passes. A parent that reads the worker's reply will see either the test
output pasted, or "produced no output"; on the second, dispatch once more.

What it costs. Wall seconds are from an uncontrolled clock; "prefill" is
the characters the local server receives per run. On oMLX most of it is
cache hits (86% of the worker's input tokens in direct mode), so prompt
length is a token cost more than a wall-clock one. Fifteen runs each; full tables in
[ablation-summary.md](research/ladder/ablation-summary.md).

| setup | pass | wall s | Mellum requests per run (max) | prefill, k chars per run |
| --- | --- | --- | --- | --- |
| bare Pi, Mellum as the agent | 8/15 | 51 | 13.1 (30) | 297 |
| your profile, Mellum as the agent | 10/15 | 72 | 13.7 (26) | 1,055 |
| worker alone (direct, v5) | 15/15 | 54 | 14.3 (27) | 308 |
| worker via your Pi (delegated, v5) | 15/15 | 54 | 11.1 (16) | 221 |

| wall s per rung | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- |
| bare Pi | 14 | 39 | 22 | 53 | 128 |
| your profile | 55 | 81 | 54 | 84 | 85 |
| worker alone | 18 | 36 | 21 | 87 | 108 |
| delegated | 30 | 38 | 24 | 77 | 99 |

Read it as: running Mellum in your full profile is the slow way (three to
four times bare Pi on the easy rungs, five times the prefill, from the 17k
character system prompt and skill files on every request); the worker
alone costs about what bare Pi costs and passes; delegation adds 10–15 s of
parent work on the small rungs and gives it back on the three-file ones,
where the briefed child needs fewer requests (14 vs 20) and never more than
16. Request counts are 11–14 per run everywhere; what differs is what each
request carries. The options for cutting this further, measured and
projected, are in [2026-10-09-worker-cost-options.md](research/2026-10-09-worker-cost-options.md).

## 4b. The second way: Mellum Mode in your own session

**Mellum Mode** (`.pi/mellum/mellum-mode.ts`) turns your current session
into the worker without a parent, a brief, or a subagent:

```bash
pi -e .pi/mellum/mellum-mode.ts -e .pi/mellum/mellum-guards.ts
```

then `/mellum <task>`: the session switches to Mellum, runs the task, and
switches back when the agent settles. For a longer back-and-forth use
`/mellum on`, type as many prompts as you like, and `/mellum off`. While the
mode is on, the model is Mellum, the tools are the worker's seven, and
every request is rewritten before it leaves: the system prompt is v5, the
messages are only those since `/mellum on` (Superpowers' bootstrap and
your earlier conversation are not sent), and pi-subagents' re-added tools
are removed. Your session keeps everything, so after `/mellum off` your
usual model sees what Mellum did.

Measured in the ladder ([A14](research/ladder/ablation-a14-mellum-mode/README.md)),
same profile and sampling as "Mellum as the primary agent" above: 10/15
becomes 14/15, rung 5 from 0/3 to 3/3, the model reads 606 characters of
prompt instead of 17k, and the wall time is the same (prefill is cached;
the time is generation). What you give up against delegation is the
parent's independent test run afterwards; run the tests yourself.

Cautions. The ladder measured the headless path; the interactive path
(`on`, a second `on`, a task, `off`, a parent turn, a second `off`, the
one-shot form) is exercised by `uv run python -m ladder.probe_mode_rpc`
over Pi's RPC mode, which showed each request carrying exactly the
expected prompt, history and tools; the refusal to auto-compact while on
is unit-tested. Pi loads `-e` extensions
first, so the filter runs before any package's payload hook; none of
Superpowers, pi-subagents or context7 rewrites the payload today. Mellum's
tool results stay in your session, so a long task leaves your usual model
a large next request. Auto-compaction is refused while the mode is on
(`/compact` still works); run `/mellum off` before a long parent turn.
The `-e` paths are relative to the repository root.

## 5. Measuring

```bash
uv run python -m ladder.run_ladder --mode direct   --guards --profile baseline --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --out docs/research/ladder/<name>
uv run python -m ladder.run_ladder --mode delegated --profile baseline --guards --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --deadline 900 --out docs/research/ladder/<name>
uv run python -m ladder.run_ladder --mode primary   --profile baseline --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --deadline 600 --out docs/research/ladder/<name>           # your profile, Mellum as the model
uv run python -m ladder.run_ladder --mode mode      --profile baseline --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --deadline 600 --out docs/research/ladder/<name>   # Mellum mode in your profile
uv run python -m ladder.run_ladder --mode primary   --profile baseline --plain --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --deadline 600 --out docs/research/ladder/<name>   # bare Pi: no extensions, skills, or context files
MELLUM_GUARDS='{"emptyFinalNudge":3,"loopBreaker":true}' uv run python -m ladder.run_ladder --mode direct --guards --profile tuned ...   # override which guards run; recorded as guards_env
uv run python -m ladder.summarize docs/research/ladder/<a> docs/research/ladder/<b>
```

Each run directory holds `run.json`, `trace.jsonl` (every request and tool
event), `stdout.txt` (Pi's JSON stream), `final.md`, `diff.patch`, and in
delegated mode `brief.md`. `ladder/rescore.py` recomputes scores offline.
Every column in `table.md` is a pathology recorded in `../local-ai-pi` or
`../satyrn-evals`; a run passes only on its fixture's own tests. Wall times
are recorded and untrusted. Three repeats are a gate, not an error rate.

## 6. What is settled and what is not

Settled by measurement:

- The worker prompt's two completion facts were the lever (11/15 → 15/15).
- Of the settings, only the request cap has a measurable effect (it is a
  request value, sent by Pi); the penalty, thinking budget and tool-result
  cap do not, with the caveat that 1c→1d changed the cap and the penalty
  together ([1c/1d](research/ladder/phase1d-tuned-effective/README.md)).
- No `write` shrank an existing file and no test file was edited in 240
  direct runs except one (A4, reverted). The loop breaker as shipped
  (repeats forgotten after any edit, write, or bash call), replayed over
  all 330 runs, would have refused nothing; its earlier form refused one
  legitimate re-read after an edit in two passing runs and was corrected.
- A frontier parent scopes and verifies natively; the child never needs the
  user's sentence.

Not settled:

- The empty-final nudge, capped at 3 with the loop breaker live, in direct
  mode: 15/15, seven nudges in six runs, every nudged run green
  ([phase 2b](research/ladder/phase2b-guards-bounded/README.md)); without
  the extension, 13/15 ([A1](research/ladder/ablation-a1-noguards/README.md)).
- **The nudge does not fire inside a pi-subagents child.** Zero nudges in
  sixty delegated runs while eleven children "produced no output"; the
  parent's re-dispatch is what recovers them. First backlog item.
- The Markdown brief as a mediator: chunked into one prompt per step it
  passes everything at 2.4× the cost; as one prompt with step-wise
  "reply" instructions it drops to 11/15 because the model stops at the
  first reply ([A15/A16](research/ladder/ablation-a15-chunked-brief/README.md)).
  The sentence plus the worker prompt stays the cheapest reliable input.
- pi-subagents appends an "Intercom orchestration channel" block (about
  1,500 characters) to the child prompt even with `contact_supervisor`
  excluded; `intercomBridge.mode: off` removes it ([A11](research/ladder/ablation-a11-delegated-nointercom/README.md)).
- Mellum as the primary agent is viable through rung 4 (10/15 overall) and
  fails rung 5; the worker's gain is at the top of the ladder, not an escape
  from a broken primary mode.

Follow-ups and the research record: [docs/research/](research/), the
[spec](superpowers/specs/2026-10-08-mellum-worker-recipe-design.md), and the
backlog at the end of the [phase-3 plan](superpowers/plans/2026-10-08-mellum-worker-ladder-phase-3.md).
