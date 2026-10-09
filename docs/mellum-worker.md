# Mellum 2.1 as a worker agent under Pi

**Status: draft written overnight 2026-10-08/09; result tables marked TODO are filled from the ladder records as they land.**

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
bootstrap, no delegation, and a prompt made of facts about its tools and the
test command.

What it is good for, measured: one-line fixes, adding a function with its
test, a rename across two files, and three-file changes with a named failing
test. What it is not: exploration, design, or scoping a task from a symptom
on its own (see the ladder results below).

## 2. Inference server (oMLX)

Serve `Mellum2.1-12B-A2.5B-Thinking-6bit` on oMLX 0.6.4 as in the main
[README](../README.md): 56,000-token context window, native hybrid cache,
cache quantization off, one concurrent request.

**Which settings actually apply.** oMLX gives a request's sampling and cap
values precedence over the per-model profile. Pi sends `max_tokens`,
`temperature`, `top_p`, `top_k`, `min_p`, `seed`, and `presence_penalty` on
every request from its `models.json` entry. So:

| setting | where it is decided | value used |
| --- | --- | --- |
| `max_tokens` | Pi `models.json` → `maxTokens` | 16,384 (model-card per-turn budget); a 4,096 cap cut off one three-file run mid-thought ([phases 1c/1d](research/ladder/phase1d-tuned-effective/README.md)) |
| temperature / top_p / top_k | Pi `models.json` → `samplingParams`, else Pi defaults | Pi default is 1 / 0.95 / 20 (the model card's agentic sampling) |
| presence / repetition penalty | request | 0 / 1.0 — a presence penalty of 0.5 changed nothing measurable (1c vs 1d: 13/15 vs 14/15, same request and error counts) |
| thinking budget | server profile only | off — a 4,096-per-block budget was never triggered in 15 runs; the request cap is what binds |
| `max_tool_result_tokens` | server profile only | off — the largest tool result in 30 runs was 2,639 characters |
| `forced_ct_kwargs: ["enable_thinking"]` | server profile only | on — a client cannot switch thinking off |

Verify with one request through the proxy or Pi's `before_provider_request`
hook (`ladder/record-pi.js`) that the values you expect are the values sent;
the ladder records them per run as `effective_params`.

The oMLX admin API is at `/admin/api/models/<id>/settings` (no auth when
`skip_api_key_verification` is on). `ladder/omlx_profiles.py` switches
profiles with a snapshot and a verified restore.

## 3. Pi setup

Project-local, nothing in `~/.pi/agent` changes:

- `.pi/agents/mellum-worker.md` — the worker. Each frontmatter line removes
  something: `systemPromptMode: replace` (no Pi base prompt),
  `inheritProjectContext/GlobalContext/Skills: false` (no AGENTS.md, no skills
  catalog), `extensions:` empty (no Superpowers in the child; pi-subagents warns
  about this on every launch — intended), `tools:` the seven file tools, and
  `acceptance: level none` (the parent verifies by running the tests; an
  acceptance contract competed with the reply format and recorded a correct
  run as rejected). Nothing else: the child has no `subagent` tool, so it
  cannot launch descendants or reach a supervisor, and pi-subagents' default
  launch context is `fresh`.
- `prompts/mellum-worker.md` (v4) — the body, duplicated into the agent file;
  a test keeps them identical. Twelve facts and no procedure: what each tool
  does, how to find the test command, *the task is complete only when the
  test command exits 0*, and *if it fails, read, change, run again*. Those two
  sentences took rung 5 from 0/3 to 3/3 ([phase 0b](research/ladder/phase0b-baseline-v3/README.md));
  the six-step procedure v3 carried was measured and removed ([ablation A2](research/ladder/ablation-a2-v4a/README.md)).
- `.pi/extensions/mellum-guards.ts` — child-only guards, loaded through
  `subagentOnlyExtensions`. On by default: the empty-final nudge (cap 3)
  and the loop breaker. Dormant: new-file-only `write`, step budget. See §6.
- No parent-side skill. One existed; it was read in 2 of 15 runs and the
  pass rate was 15/15 with or without it ([phase 3b](research/ladder/phase3b-delegated-skill/README.md)),
  so it was removed. Its content is §4's one paragraph on briefing.
- `~/.pi/agent/models.json` omlx entry: `contextWindow 56000`, `maxTokens
  16384`, `thinkingFormat: qwen-chat-template`.

Try it safely:

```bash
uv run python -m ladder.sandbox 1   # prints a disposable copy of rung 1 with .pi/ included
```

then `cd` there, start `pi`, and say *Use mellum-worker to do this: the cart
total ignores quantity, fix it*. Never run the worker inside `fixtures/`
itself; it edits in place.

## 4. Using the worker

In a normal Pi session, name the worker: "Use mellum-worker to do this: …".
Your parent scopes the task, writes the brief, launches the child, and — in
every measured run — runs the tests itself before reporting. Check the
child's final text, not just the parent's summary: the child's one recorded
pathology is a turn that ends with `stop` and no text.

The ladder's five sentences, as a user would type them, and what happened:

| rung | sentence | worker alone (direct, greedy; cap 4,096 / cap 16,384) | via your Pi (delegated) |
| --- | --- | --- | --- |
| 1 | the cart total ignores quantity, fix it | 3/3 / 3/3 | 3/3 |
| 2 | add a balance() that sums the entries, with a test | 3/3 / 3/3 | 3/3 |
| 3 | rename fetch_rows to load_rows everywhere | 3/3 / 3/3 | 3/3 |
| 4 | make the failing test pass (three failing tests, three files) | 2/3 / 2/3 | 3/3 |
| 5 | the export is missing the totals row (same, plus a decoy, no test named) | 2/3 / 3/3 | 3/3 |

Mellum as the *primary* agent in your own profile, given the same sentences
([phase 0c](research/ladder/phase0c-primary-operator/README.md)): 3/3, 2/3,
3/3, 2/3, 0/3. It reads and follows the Superpowers skills; it fails when a
skill asks a question nobody answers, when a turn ends empty, and on the
three-file change by symptom. Bare Pi with no extensions or skills
([phase 0c plain](research/ladder/phase0c-primary-plain/README.md)): 3/3, 3/3,
2/3, 0/3, 0/3, with four empty finals, three false "fixed" claims, and one
rewritten test file. The worker alone under the same model and harness is
15/15 ([phase 2b](research/ladder/phase2b-guards-bounded/README.md)).

Where it stops working: rung 5 is a three-file change described only by a
symptom. Alone, the worker's failures there are honest ("tests still
failing") or silent (empty final). With a parent that scopes first, it
passes.

## 5. Measuring

```bash
uv run python -m ladder.run_ladder --mode direct   --guards --profile baseline --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --out docs/research/ladder/<name>
uv run python -m ladder.run_ladder --mode delegated --guards --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --deadline 900 --out docs/research/ladder/<name>
uv run python -m ladder.run_ladder --mode primary   --profile baseline --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --deadline 600 --out docs/research/ladder/<name>           # your profile, Mellum as the model
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
- Of the server-side settings, only the request cap has a measurable effect;
  penalty, thinking budget and tool-result cap do not ([1c/1d](research/ladder/phase1d-tuned-effective/README.md)).
- The write-clobber and loop pathologies did not occur in 135 direct runs;
  the loop breaker, replayed exactly, would have touched one thrashing run.
- A frontier parent scopes and verifies natively; the child never needs the
  user's sentence.

Not settled:

- The empty-final nudge, capped at 3 with the loop breaker live: 15/15,
  seven nudges in six runs, every nudged run green, no run needed a third
  nudge, no loop-breaker refusal ([phase 2b](research/ladder/phase2b-guards-bounded/README.md)).
  This is now the guard default. The empty turn itself is a model behaviour
  the prompt does not change; it is handled, not fixed.
- Mellum as the primary agent is viable through rung 4 (10/15 overall) and
  fails rung 5; the worker's gain is at the top of the ladder, not an escape
  from a broken primary mode.

Follow-ups and the research record: [docs/research/](research/), the
[spec](superpowers/specs/2026-10-08-mellum-worker-recipe-design.md), and the
backlog at the end of the [phase-3 plan](superpowers/plans/2026-10-08-mellum-worker-ladder-phase-3.md).
