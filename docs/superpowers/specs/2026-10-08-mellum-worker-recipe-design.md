# Mellum worker recipe: design

**Date:** 2026-10-08
**Status:** approved design, awaiting implementation plan
**Scope:** this repository (`mellum-mlx`), the local oMLX server, the operator's Pi and OpenCode installations

## 1. Intent

A person working in their normal Pi or OpenCode session, with Superpowers
loaded and their usual hosted model driving, can hand an ordinary, imprecise
coding request to a local Mellum 2.1 worker and get a correct result. The
recipe is measured by a graded prompt ladder, and the README lets someone else
reproduce the server settings, the harness setup, and the ladder.

Success looks like: a known set of rungs that pass, a known rung where it stops
working, and a table that says what each change (server profile, guards,
parent-side scoping) bought.

## 2. What the research established

The recovery report at
[docs/research/mellum-recovery-2026-10-07/report.md](../../research/mellum-recovery-2026-10-07/report.md)
and the four briefs beside it settle these points; this design does not
re-litigate them.

- Whole-document 50k-token literal retrieval is a capability ceiling of the
  original checkpoint (2.5B active parameters, 4 KV heads, 21 of 28 layers
  sliding-window). Not conversion, not MLX, not oMLX.
- The agent-loop failures (skill names dispatched as agents, retries after
  explicit errors, a wrong request ID) were produced by Mellum as the
  *parent* under the Superpowers bootstrap and pi-subagents supervisor
  protocol. The same weakness, discriminating between look-alike strings,
  underlies both failure classes.
- A clean profile (thinking on, no bootstrap, no skills catalog, file tools
  only, prompts of a few thousand tokens) completed nine of nine literal
  retrievals and a three-test coding fix in both Pi and OpenCode.
- Verified on 2026-10-08 in this session: an OpenCode `mellum-worker`
  subagent launched from a normal Superpowers-enabled parent session received
  no bootstrap and no skills list, fixed the coding fixture with zero tool
  errors, and all six captured requests carried the intended model and
  sampling parameters.

Two sibling projects recorded what goes wrong when a small local model is
given file tools. Their findings constrain this design (section 4):
`../local-ai-pi/docs/evals/slm-struggles.md` and
`../satyrn-evals/docs/pathologies.md`.

## 3. Shape

```
user (vague sentence)
  └─ parent session: hosted DeepSeek Flash 4.1, Superpowers on, normal config
       └─ task tool ─► mellum-worker (child session)
                         model:   omlx/Mellum2.1-12B-A2.5B-Thinking-6bit
                         prompt:  facts-only worker prompt (B: self-scoping)
                         tools:   read, grep, find/glob, ls, bash, edit, write
                         no:      bootstrap, skills catalog, global AGENTS.md,
                                  subagent/task, supervisor, todo, web
```

Only Mellum is resident locally, so the 16 GB serving target is unchanged.

Two launch modes exist because the parent rewrites the task before Mellum sees
it:

- **direct** — the worker alone receives the user's sentence. Measures the
  worker (B). Gate for phases 0–2.
- **delegated** — the real parent receives `@mellum-worker <sentence>` and
  composes the child's task. Measures the whole recipe. Recorded from phase 0,
  gate for phases 3–4.

## 4. Decisions and the evidence behind them

1. **B (worker self-scoping) before A (parent-side scoping skill).** The
   point of the ladder is to see what the server and harness fixes bought on
   their own. A is added in phase 3 only for rungs that still fail.
2. **`write` stays in the tool set.** The operator's earlier instinct, and
   this design's first draft, removed it. The sibling records say both
   alternatives are worse:
   - `write`-only envelopes destroyed files: a model wrote the changed
     fragment as the whole file, 942 lines → 2, 717 → 3
     (`local-ai-pi/docs/superpowers/research/2026-08-11-morning-summary.md`).
   - Denying a tool moves the behaviour: a child routed a denied `ls` through
     a shell tool (`local-ai-pi`, LESSONS §8); pi-subagents' child permissions
     cannot restrict bash at all; satyrn-evals needed a heredoc parser because
     file writes through `cat <<EOF` are invisible to `write`/`edit`
     telemetry.
   - Without `write`, rung 4's new module and any near-miss path have no
     observable channel.
3. **Tool policy is enforced in the tool-call path, never by prompt rule.**
   local-ai-pi tested five prompt interventions: the three that supplied a
   missing fact worked, the two that supplied a rule of conduct were
   falsified. The worker prompt therefore states facts ("`write` replaces the
   entire file; `edit` changes a region", "the test command is …"). Rules such
   as "use `edit` for existing files" become guards (phase 2).
4. **Measure before guarding.** Phase 0–1 run with no guards and ladder
   columns for every recorded pathology. A guard is added in phase 2 only for
   columns that are non-zero; otherwise it ships disabled and the README says
   it was not needed.
5. **Guided grammar is dropped.** oMLX's `guided_grammar` is one EBNF applied
   to the whole output per model, unusable for free-form turns with tool
   calls. The unknown-agent failure class is already removed structurally:
   the worker has no `task`/`subagent` tool and the parent's `task` tool
   validates names.
6. **Exit zero proves nothing.** Every outcome is scored from the fixture's
   own tests and from captured tool/request records, as the recovery bundle
   did.
7. **Wall-clock is recorded and labelled untrusted** (local-ai-pi: two
   published timings retracted in one night).

## 5. Components

### 5.1 Inference server profiles

Two oMLX profiles for `Mellum2.1-12B-A2.5B-Thinking-6bit`, switched by the
ladder runner through `PUT /api/models/{model_id}/settings` (admin API key from
`~/.omlx/settings.json`), with `~/.omlx/model_settings.json` snapshotted before
and restored after every run. A forgotten restore silently broke
reproducibility in local-ai-pi; the restore is structural here.

| Setting | baseline (today) | tuned |
| --- | --- | --- |
| `max_context_window` | 56,000 | 56,000 |
| `max_tokens` | 4,096 | 16,384 (model-card per-turn budget) |
| `thinking_budget_enabled` / `_tokens` | off | on / 4,096 — forces `</think>` so a turn can never end inside thinking |
| `presence_penalty` | 0 | 0.5 — targets the verbatim re-scan loop |
| `repetition_penalty` | 1.0 | 1.0 (penalises legitimately repeated code tokens; left off) |
| `temperature` / `top_p` / `top_k` / `force_sampling` | 1 / 0.95 / 20 / on | same; a request's `temperature: 0` overrides for the ladder's greedy runs |
| `max_tool_result_tokens` | unset | 4,000 — bounds the tool-output explosion |
| `chat_template_kwargs` / `forced_ct_kwargs` | unset | `{"enable_thinking": true}` / `["enable_thinking"]` — thinking cannot be switched off by a client |
| `guided_grammar_enabled`, TurboQuant, cache quantization | off | off |

Why 4,096 and not more for the thinking budget: with `preserve_thinking: true`
prior thinking is re-sent every step, so 12 steps × 6k would exceed the 56k
context. "Largest prompt tokens" is a gate column. If it approaches 50k, the
documented contingency is a `tuned-nopreserve` variant with
`preserve_thinking: false`, run as its own ladder pass.

Verification steps recorded in the README: `/v1/models` shows the model; a
2+2 request answers; a request that provokes long thinking returns a response
whose reasoning closes at the budget; a request with `max_tokens` above the
profile's cap is clamped rather than rejected (to confirm in phase 1; if
rejected, the harness limits are switched per profile instead).

### 5.2 Harness limits (set once, to match the server)

- OpenCode `provider.omlx.models.<id>.limit`: `context 56000, input 51904,
  output 16384`. The entry was corrected to 56000/4096 on 2026-10-08; output
  moves to 16384 with the tuned profile.
- Pi `~/.pi/agent/models.json` omlx entry: `contextWindow 131072 → 56000`;
  `maxTokens 16384` already; `thinkingFormat: qwen-chat-template` already.
- OpenCode global `model` / `small_model`: `deepseek/deepseek-v4-flash` is
  marked deprecated in models.dev and no longer resolves in a fresh process;
  the operator is moving both to `deepseek/deepseek-flash` and removing the
  Z.AI provider.

### 5.3 Worker definitions (project-local)

**Pi** — `.pi/agents/mellum-worker.md`:

```yaml
---
name: mellum-worker
description: Bounded coding task on the local Mellum model
model: omlx/Mellum2.1-12B-A2.5B-Thinking-6bit
thinking: high
advertise: true
systemPromptMode: replace
inheritProjectContext: false
inheritGlobalContext: false
inheritSkills: false
extensions:
subagentOnlyExtensions:        # phase 2: ./.pi/extensions/mellum-guards.ts
tools: read, grep, find, ls, bash, edit, write
allowedAgents:
defaultContext: fresh
acceptanceRole: writer
---
<worker prompt body>
```

`contact_supervisor` is excluded (the request-ID protocol Mellum failed);
`extensions:` empty means no Superpowers in the child; `allowedAgents:` empty
denies descendants. No same-name user agent exists, so nothing is shadowed.

**OpenCode** — `.opencode/agents/mellum-worker.md` (phase 4), frontmatter:
`mode: subagent`, same model, `temperature: 0`, `top_p: 1`, `steps: 12`,
`options.chat_template_kwargs {enable_thinking, preserve_thinking}`,
`tools: {skill: false, task: false, todowrite: false, todoread: false,
webfetch: false, websearch: false}`, `permission` allowing read/grep/glob/
list/edit/write/bash. The body is the same worker prompt. The Superpowers
plugin skips bootstrap injection for sessions with a `parentID`; `skill:
false` removes the skills section (`session/system.ts:108`). Global and
project `AGENTS.md` are still injected (no per-agent filter in
`session/instruction.ts`); the README says so and recommends keeping the
global file small. The global `mellum-worker` entry added to
`~/.config/opencode/opencode.jsonc` on 2026-10-08 is removed once the project
one passes the ladder.

**Worker prompt** — `prompts/mellum-worker.md`, one text shared by both
definitions. Facts and a procedure, no rules of conduct:

- What the tools do: `grep` finds a literal in files; `read` shows a file or a
  line range; `edit` replaces one exact region of an existing file; `write`
  creates a file and replaces the entire content of an existing one; `bash`
  runs a command in the working directory.
- How to find the test command: a `pyproject.toml` with pytest means
  `uv run pytest`; a `package.json` with a test script means `npm test` or
  `node --test`; a command given in the task is the command.
- Procedure: restate the task in one line; find the files by searching for
  the identifiers in the task; read the matching regions and the tests that
  cover them; make the smallest change; run the tests; report files changed,
  the test output verbatim, and anything not done.
- What to say when the task cannot be located: name what is missing.

The prompt is versioned (`v2`) and the ladder records which version ran.

### 5.4 Fixtures

`fixtures/<rung>/`, each a self-contained project with a committed baseline, a
`.gitignore` (`.venv/`, `__pycache__/`, `.pytest_cache/`), and no acceptance
file in the workspace — the fixture's own tests are the check. Python fixtures
pin pytest in `pyproject.toml` with a committed `uv.lock`; the runner warms
the uv cache once so runs are offline.

| Rung | Project | User sentence | Pass check |
| --- | --- | --- | --- |
| 1 | `calculator/` (the bundle's JS fixture) | "the cart total ignores quantity, fix it" | `node --test` 3/3; test file byte-identical |
| 2 | `ledger/` one module, one test file | "add a `balance()` that sums the entries, with a test" | every baseline test node ID still collected and passing; at least one new node ID containing `balance`; `uv run pytest` passes |
| 3 | `rename/` symbol used in two files | "rename `fetch_rows` to `load_rows` everywhere" | pytest passes; zero `fetch_rows` in tree; both source files changed |
| 4 | `feature/` three source files, one failing test present | "make the failing test pass" | pytest passes; ≥ 2 source files changed; test file byte-identical |
| 5 | `edge/` as 4 plus a decoy module with a near-miss name; no test named in the sentence | "the export is missing the totals row" | pytest passes; decoy byte-identical; test file byte-identical |

Each file stays under 60 lines so whole-file writes sit far below any output
cap; the ladder measures the model, not the 30 KB wall local-ai-pi hit.

### 5.5 Ladder runner

`ladder/run_ladder.py`, stdlib only, modelled on the bundle's
`run_opencode.mjs` / `run_pi.mjs`:

- Flags: `--harness pi|opencode`, `--mode direct|delegated`,
  `--profile baseline|tuned`, `--rung N` (repeatable), `--repeat N`
  (gate runs use 3), `--sampling greedy|card`, `--prompt-version`,
  `--deadline SECONDS` (per run; a hit is a harness bound, recorded, not a
  model error), `--out DIR`.
- Per run: copy the fixture to a scratch directory, `git init` + commit the
  baseline, apply the server profile and confirm it through the admin GET,
  launch, wait, score, write `run.json` and append a row to `table.md`,
  restore the server profile at exit (also on failure).
- **Pi direct:** `pi -p --no-extensions --no-skills --no-context-files
  --no-session --thinking high --model omlx/<id> --tools
  read,grep,find,ls,bash,edit,write --append-system-prompt prompts/mellum-worker.md
  -e ladder/record-pi.js "<sentence>"`. This is the recovery report's verified
  clean profile. `record-pi.js` is the bundle's extension, copied, with the
  request-count abort removed (the deadline bounds the run) — it records every
  provider request payload, tool call and tool result through
  `before_provider_request` / `tool_call` / `tool_result`.
- **Pi delegated:** a temporary `PI_CODING_AGENT_DIR` mirroring the real
  profile (settings, `models.json`, `auth.json`, `AGENTS.md`; package
  directories symlinked) so the parent has its normal Superpowers
  environment, launched with `pi -p "@mellum-worker <sentence>"`-style
  wording that names the worker. The child's requests are captured by
  `record-pi.js` listed in the worker's `subagentOnlyExtensions` for ladder
  runs only (the runner adds it through a project `.pi/settings.json`
  `agentOverrides`, not by editing the agent file).
- **OpenCode direct (phase 4):** the worker is given `mode: all` for the
  ladder so `opencode run --pure --agent mellum-worker` can address it
  directly; `--pure` keeps the bootstrap out of a top-level session.
- **OpenCode delegated (phase 4):** `opencode run --agent build
  "@mellum-worker <sentence>"` with a scratch-dir `opencode.jsonc` that
  points `omlx` at the capture proxy, as verified on 2026-10-08.
- `ladder/proxy.py` is this session's capture proxy, extended to record each
  streamed response's `finish_reason` and `usage` from the final SSE chunk.
- Tool/request evidence for OpenCode comes from the proxy plus the bundle's
  `inspect_opencode.mjs` (read-only SQLite, scoped to the run's sessions).

### 5.6 Scorer

`ladder/score.py`: pure functions from recorded evidence to a `Score`, so the
scorer is unit-tested against committed transcripts and can be re-run offline
(local-ai-pi's replay seam). Columns, each tied to a recorded pathology:

| Column | Source | Pathology it detects |
| --- | --- | --- |
| `passed` | fixture check | — |
| `tests_unchanged` / `baseline_tests_present` | byte compare / `pytest --collect-only -q` | tests-vanished |
| `files_changed`, `files_created` | `git add -A && git diff --cached --stat` | untracked files invisible to `git diff HEAD` |
| `tool_calls_by_name`, `tool_errors` | records | — |
| `edit_anchor_failures`, `noop_edits` | `edit` results | stale anchors; no-op edits reported as success |
| `write_existing`, with line count before/after | `write` args vs baseline tree | fragment-as-whole-file clobber |
| `bash_file_mutations` | heredoc/redirect detection on `bash` args (satyrn's `cell_evidence.py` rules) | default-deny evasion |
| `max_identical_streak` | call key = tool + stable-sorted args | 245× `ls -R`; 281× `read` |
| `thinking_budget_hits` | response `finish_reason` / forced close | — |
| `largest_prompt_tokens` | request usage | context growth with preserved thinking |
| `deadline_hit`, `steps` | runner | no turn cap |
| `wall_seconds`, `omlx_peak_rss` | runner | recorded, labelled untrusted |

A run is a gate pass only if `passed` and `tests_unchanged`; the other columns
are findings.

### 5.7 Guards (phase 2, conditional)

`.pi/extensions/mellum-guards.ts`, loaded only in the child through
`subagentOnlyExtensions` (and `-e` in direct mode). Pure `ToolCall →
Decision` functions in the local-ai-pi shape, returning `{block: true,
reason}` from Pi's `tool_call` hook:

1. **new-file-only `write`** — refuse a `write` whose path exists; the reason
   states the fact: "`<path>` exists; `write` replaces the entire file — use
   `edit`". Enabled only if `write_existing` was non-zero in phases 0–1.
2. **loop breaker** — `loop-breaker.ts` from local-ai-pi, unchanged (window
   20, threshold 5, keyed on tool + arguments, trips on successful repeats).
   Enabled only if `max_identical_streak` reached 5.
3. **step budget** — block every tool call past N with a reason to
   summarise and stop (the "graceful turn budget" candidate). Enabled only if
   `deadline_hit` was non-zero.

The OpenCode port (phase 4) uses `tool.execute.before` (throw to block),
scoped to the worker by a session → agent lookup through the client, the way
the Superpowers plugin resolves `parentID`.

### 5.8 Parent-side skill (phase 3, conditional)

`.pi/skills/delegate-to-mellum/SKILL.md` (and `.opencode/skills/` in phase 4):
when the parent decides to use the worker, it first does the scoping itself —
find the files with `grep`/`find`, name the symbols, pick the test command,
write acceptance criteria — then dispatches a brief in a fixed template. Added
only for rungs that fail in delegated mode after phase 2, and measured against
delegated-without-skill.

### 5.9 README

Replaces the current README's "Recommended path"; the conversion section
stays.

1. What this is — the verdict, linking the research.
2. Inference server — the tuned profile table with a reason per value; how
   to apply (admin UI, `model_settings.json`); how to verify.
3. Pi setup — the agent file line by line (what each removes and why), how
   the parent sees the worker, the guard extension.
4. OpenCode setup — the agent file, the `tools`/`permission` block, what
   OpenCode cannot isolate (AGENTS.md) and what to do, the deprecated-model
   gotcha.
5. Using the worker — what Mellum is for and not; the five ladder sentences
   as worked examples: the user's sentence, what the parent sent, what Mellum
   did, the measured result; rung 5 written as "here is where it stops".
6. Measuring — `uv run ladder/run_ladder.py …`, reading the table.
7. Follow-ups — the Transformers logit comparison at 12–16k, the five
   canonical-vLLM controls for the Mellum maintainers, the exact historical
   replay. Decided, not built.

## 6. Phases and gates

| Phase | Builds | Runs | Gate to proceed |
| --- | --- | --- | --- |
| 0 | fixtures, runner, scorer (TDD), prompt v2, `.pi/agents/mellum-worker.md`, harness limits | Pi direct, baseline profile, rungs 1–5 × 3; Pi delegated recorded | runner and scorer tests green; a complete table exists |
| 1 | — | same, tuned profile | per-rung comparison table written; `largest_prompt_tokens` < 50k |
| 2 | guards for non-zero columns only | Pi direct, tuned, rungs 1–5 × 3 | guarded columns at zero or the guard recorded as ineffective |
| 3 | `delegate-to-mellum` skill | Pi delegated with/without skill on rungs failing delegated | table row per rung |
| 4 | `.opencode/agents/mellum-worker.md`, guard port, remove global entry | OpenCode direct and delegated, tuned | parity table Pi vs OpenCode |
| 5 | README | — | a second person can follow sections 2–6 |

Each phase ends with a short record under `docs/research/ladder/` (table plus
the `run.json` files), the way the recovery bundle kept evidence.

## 7. Testing

- `tests/test_score.py`: the scorer over committed example records — one
  passing run, one clobber, one loop, one heredoc write, one deadline.
- `tests/test_fixtures.py`: every fixture's baseline fails or passes exactly
  as its rung specifies (rung 4/5 fail before the change; rung 1–3 pass).
- `tests/test_runner.py`: profile snapshot/restore round-trips without a
  server (admin client behind an interface with a fake).
- Smoke: `run_ladder.py --rung 1 --repeat 1` on each harness before any gate
  run.

## 8. Risks and verification steps

| Risk | Handling |
| --- | --- |
| oMLX rejects `max_tokens` above the profile cap instead of clamping | verify in phase 1; fall back to switching harness limits per profile |
| Forced `</think>` leaves Mellum unable to emit a tool call | `thinking_budget_hits` column plus outcome; lower the budget or disable if the column correlates with failure |
| Preserved thinking grows the prompt past 56k | gate column; `tuned-nopreserve` contingency |
| Parent in delegated mode does the task itself instead of delegating | prompt names the worker explicitly; `delegated` column records whether a child session existed |
| uv needs the network inside fixtures | runner warms the cache; `uv run --offline` afterwards |
| Pi version drift between runs | runner records `pi --version`, `opencode --version`, oMLX version and model settings in every `run.json` |
| Greedy MoE decoding is not bit-reproducible | three repeats per gate; pass counts, not single verdicts |

## 9. Out of scope

Reconverting weights; changing RoPE, sliding window, or cache type;
TurboQuant; LoRA on the tool protocol; the caix/Core AI port; the
Transformers logit comparison and the JetBrains bundle (documented as
follow-ups); a physical 16 GB machine test.

## 10. Self-review

- No placeholders: every setting has a value, every rung a check, every column
  a source.
- Consistency: `write` is in the tool set everywhere; guards are conditional
  everywhere; direct mode gates phases 0–2 and delegated gates 3–4 in both
  section 3 and section 6.
- Scope: one implementation plan can cover phases 0–2; phases 3–5 depend on
  measured results and are planned when phase 2 closes.
- Ambiguity resolved: "tests unchanged" means byte-identical for rungs 1, 3,
  4, 5 and node-ID preservation for rung 2; "pass" means the fixture check,
  never exit status.
