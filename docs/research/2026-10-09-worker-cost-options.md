# The worker's cost: where it goes, and the ways to cut it

Date: 2026-10-09. Inputs: the ladder records (`ladder/`), a survey of what
the Pi community has built for bounded execution on a cheap model (2026-10-09,
summarised below with links), Pi's own extension and SDK docs, and the
`pi-circuitbreaker` fork's notes on small-model harnessing.

## 1. Where the cost is, measured

Per task, delegated recipe as it ships ([A10](ladder/ablation-a10-delegated-v5/README.md)),
15 runs, five rungs:

| item | value | note |
| --- | --- | --- |
| wall, mean | 54 s | 30/38/24/77/99 s by rung |
| parent (DeepSeek Flash) | 6.5 turns, 2,900 output tokens, 19k input + 100k cache-read tokens | reads code, writes a 1,100-char brief, launches, runs the tests itself |
| child (Mellum) requests | 11.1 per run, max 16 | |
| child system prompt | 2,711 chars | **643 ours**; 2,068 pi-subagents (521 preamble + 1,582 intercom block + cwd) |
| child prefill | 221k chars per run | 86% of input tokens are oMLX cache hits (measured on the direct worker, A3) |

The same tasks with the worker alone (direct mode, [A3](ladder/ablation-a3-v4b/README.md)):
54 s, 14.3 requests, 308k chars prefill. Bare Pi with Mellum: 51 s and 8/15.
The operator's full profile with Mellum: 72 s and 10/15, 1,055k chars prefill.

So: the parent round trip costs 10–15 s on the small rungs and pays for
itself on the three-file ones (the briefed child needs 14 requests instead
of 20). Two thirds of what the child reads before the task is pi-subagents'
boilerplate. Prefill is mostly cached, so prompt length is a token cost,
not a wall-clock one. Wall time is dominated by the model's own generation
on rungs 4–5 (77–108 s in every setup that passes them).

**Measured after this document was first written (A12):** stripping
earlier turns' `reasoning_content` from each request halves prefill and
makes the run 60% slower, because the model regenerates what it no longer
sees (output tokens +73%, empty turns ×3). Context is the cheap side on a
cached local server; generation is the expensive side. Every option below
that filters context must leave prior thinking in place.

**Measured after (A13):** a hook that sends oMLX's request-level
`thinking_budget` works at the wire and is not enforced by this server
build for Mellum: the scheduler only builds its budget processor when a
reasoning parser is configured for the model, and none is. There is
currently no per-turn cap on Mellum's thinking through oMLX.

**Measured after (A14):** the Mellum mode (3a) is built and measured:
in the operator's own profile, same sampling, 10/15 → 14/15, rung 5 from
0/3 to 3/3, prefill −78%, wall time unchanged (70 vs 72 s). Recommendation
2 is done; it ships as `/mellum on|off`.

**Measured after (A15/A16):** the Markdown track. Chunked (one prompt
per step, one session) passes 15/15 at 2.4× the time and 2.5× the output
tokens; the same brief as one prompt drops to 11/15 because the model
stops at the first mid-brief "reply" step. Neither ships. The sentence
plus the v5 prompt stays the cheapest reliable input; the "no steps" brief
shape and verification between steps remain unmeasured.

## 2. Minor modifications to the current recipe

| change | measured? | effect | cost to adopt |
| --- | --- | --- | --- |
| `intercomBridge.mode: off` in pi-subagents' config | yes, [A11](ladder/ablation-a11-delegated-nointercom/README.md) | child prompt 2,711 → 1,220 chars, prefill −20%, 15/15, wall unchanged | one line in `~/.pi/agent/extensions/subagent/config.json`; **global**: every subagent of the operator loses `contact_supervisor` |
| `async: false` in the worker's frontmatter | no | prevents the one async-launch failure seen ([A8](ladder/ablation-a8-delegated-lean/README.md)) | one line; the parent blocks while the child runs, which it does anyway in every passing run |
| worker description tells the parent "re-dispatch once on 'produced no output'" | no | makes the recovery the parent performs unprompted (12 of 13 times) a documented contract | one line in the description, which the parent reads unconditionally |
| `outputMode: file-only` / `maxOutput` | no | caps what the child's final text costs the parent; our finals are 100–700 chars, so little to gain | frontmatter |
| `subagents_enable` loader stub | no | parent starts with a small `subagent` schema instead of the full one; saves parent tokens per turn, not time | pi-subagents setting; unverified size |
| shorter parent brief | no | briefs average 1,100 chars and name the files; the child's 14-vs-20 requests on rungs 4–5 is what the brief buys, so this is the wrong place to cut | — |

Recommended now: the first three. A11 is the measurement for the first;
the second and third need one delegated run (15 runs, 15 min) to confirm
they change nothing else.

## 3. Alternatives to pi-subagents

### 3a. A "Mellum mode" inside the main session (run in main, with guardrails)

What Pi allows, from `docs/extensions.md`: an extension can call
`pi.setModel`, `pi.setActiveTools`, `pi.setThinkingLevel`; `context` lets
it drop or add messages before each call (this is how Superpowers inserts
its bootstrap); `before_provider_request` lets it replace the whole payload
right before it is sent, including the system message. Pi ships
`examples/extensions/preset.ts`, which does model + tools + thinking as a
named preset, but appends its instructions rather than replacing.

Design: `/mellum on` sets the model to Mellum and the tools to the seven;
while on, `before_provider_request` rewrites the payload so the system
message is v5 and the messages are only those since the mode began (the
Superpowers bootstrap, the skills catalog, AGENTS.md and the parent's
history are all gone from what Mellum sees); the guard extension's hooks
run; `/mellum off` restores model, tools and the full history for the
parent. The user types the task; nobody writes a brief.

Projected cost: the direct-mode numbers (45–54 s, 12–14 requests), because
the model would see exactly what direct mode sends. Saves the parent's
turns and tokens and the 10–15 s on small rungs; on the three-file rungs
it gives up the brief, so expect direct mode's 20 requests rather than the
briefed child's 14.

Guardrails: the tool allowlist and the guard extension as in the child,
plus an exit gate the mode can run itself (the test command before
`/mellum off`). What it loses is the parent's independent verification and
scoping, which is what made rung 5 pass in every delegated phase. The
nudge is known to work in print mode; whether `agent_before_settle`
continues an interactive turn needs a probe.

Measurable headlessly: the operator profile with the mode extension forced
on, through `pi -p`, is a new runner mode and compares directly with
primary-operator (10/15, 72 s) and direct (15/15, 54 s). Build: ~150 lines
of extension plus the runner switch; one 15-run phase.

Community packages near this: `pi-profile-switch` (`/profile use <name>`
drops skills/extensions and sets model + tools, but appends instructions
and keeps Pi's base prompt), `pi-presets-plus` (same append semantics),
`pi-prompt-template-model` (a template with `model:` and `restore: true`
runs one turn on another model, but that turn sees the whole main context).
None filters the history or replaces the prompt; the 150 lines are the
difference.

### 3b. An in-process child through Pi's SDK (keep the parent, drop the boilerplate)

`createAgentSession({ model, tools, systemPrompt, sessionManager:
SessionManager.inMemory(), resourceLoader })` runs a child in the parent's
process with no skills, no extensions, no pi-subagents preamble. A custom
tool `mellum_worker(task)` in a 200-line extension would create one per
call, attach our guards, run `session.prompt(task)`, and return the final
text. The parent still scopes, briefs and verifies.

What it fixes: the child's prompt becomes v5 alone (643 chars, not 1,220
or 2,711); the nudge works because we own the loop (pi-subagents ends a
run on an empty terminal message before any continuation hook acts); no
"produced no output" termination. What it does not change: the parent
round trip. Cost: the parent's tool schema shrinks to one tool. Unverified
until built: whether `createAgentSession` inside an extension can use the
operator's oMLX model entry and whether `agent_before_settle` fires for it.

### 3c. Lighter subagent packages

From the survey: `pi-subagents-lite` (three tools, one-line descriptions,
isolated session per agent, stuck-agent watchdog), `@bermudi/pi-delegate`
(compact tool surface, child prompt = profile body only, no parent
extensions, token budgets), `@pify/subagent` (turn cap, gate shell check),
`gee666/pi-subagent` (separate process, appends to Pi's prompt). They cut
parent schema tokens and child boilerplate, which 3b also does without a
new dependency. Lower priority unless 3b proves hard.

### 3d. A direct model call from a tool

`ctx.modelRegistry.complete(model, {messages})` from a custom tool: no
session, no tools, one shot. Right for no-tool tasks (explain this
function, write this docstring). Not our case: every rung needs the file
tools.

## 4. The Markdown between the user and the executor

The brief is the one input never varied on purpose. In direct mode the
worker gets the raw sentence; in delegated mode it gets whatever the parent
improvises. Three experiments, each a `--brief` or `--chunked` switch on
the runner and a fixed Markdown document per rung in the fixtures:

1. **Brief shape, one prompt.** The task as a Markdown document in a fixed
   shape (files, change, test command, done-when, do-not-touch), handed to
   the worker directly. Measures whether structure alone moves the
   self-scoped rung 5 (direct mode's weak rung) and the request count.
   This is also what a plan document in the repository is; pi-subagents'
   packaged `worker` reads `plan.md` by default.
2. **Chunked brief, one session, several prompts.** Ordered steps, one
   prompt per step in the same session (`pi -p --session <file>` or the
   SDK's `session.prompt()` repeatedly): restate, change file A, change
   file B, run the tests, report. Each turn is bounded; "tests at the end"
   becomes a step the runner guarantees rather than a fact the model must
   honour. New scorer column: prompts per run. Question: do the empty turns
   on the three-file rungs disappear when no single turn has to plan all
   three files?
3. **Chunked with verification between steps.** The runner runs the test
   command after each edit step and feeds the failure in as the next
   prompt: the verify loop from the `pi-circuitbreaker` notes, with the
   Markdown as the step list.

Cost to build: a few hours for the driver and the per-rung briefs; three
15-run phases.

## 5. Borrowed guardrails, if a measured pathology calls for them

The survey's reference design for small models in Pi is `small-coder`
(`--no-extensions --no-context-files`, AGENTS.md as the whole prompt, and
extensions for output repair, a two-strike quality monitor, a thinking
budget, a turn cap, a read guard, tool gating and a context watchdog;
Qwen3.5-9B went from 19% to 46% on Aider Polyglot with them). Loop guards
built for the same purpose: `pi-antiloop`, `pi-loop-police`,
`pi-loop-guard`; tool-call repair: `pi-tool-repair`. Our ladder has
recorded exactly one residual pathology (the empty turn) and none of the
others these address, so they stay on the shelf until a rung shows the
need. The unseen-path guard proposed for the "sedgewick → swaggers" report
belongs in the same category: build it when a fixture reproduces the
failure.

## 6. Recommendation

1. **Adopt** `intercomBridge.mode: off` if the operator's other subagents
   do not need supervisor messaging, `async: false` in the worker, and the
   re-dispatch line in its description. One delegated run to confirm.
2. **Build and measure the Mellum mode (3a).** It is the only option that
   answers "run in main with guardrails", it is 150 lines on documented
   hooks, and it is measurable against two existing baselines. Expect it
   to match direct mode on cost and lose the parent's scoping on rung 5;
   the measurement says whether that trade is worth a `/mellum` command.
3. **Run the Markdown experiments (4), chunked first.** They are the track
   most likely to cut the child's requests on rungs 4–5, which is where the
   wall time is in every setup.
4. **Hold 3b** until 3a's measurement is in; it fixes the nudge inside a
   child, which only matters if the parent round trip stays.

## Survey sources

Verified by reading: pi-mono `docs/extensions.md`, `docs/sdk.md`,
`examples/extensions/preset.ts`, `examples/extensions/subagent/`;
pi-subagents `docs/configuration.md` (intercom bridge), `docs/agents.md`,
`src/intercom/intercom-bridge.ts`. From the survey, by link only:
https://github.com/badlogic/pi-subagent, https://github.com/pifydev/subagent,
https://github.com/AlexParamonov/pi-subagents-lite,
https://github.com/bermudi/pi-delegate, https://github.com/VincentFF/pi-profile-switch,
https://github.com/itayinbarr/little-coder, https://github.com/NoRaincheck/small-coder,
https://github.com/Romiltec/pi-gemma-agent. Unverified: `pi-agent-mode`'s
prompt semantics, whether oMLX honours Pi's experimental constrained
sampling, two Discord threads that returned errors.
