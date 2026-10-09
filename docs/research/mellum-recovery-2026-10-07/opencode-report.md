# OpenCode follow-up: Mellum 2.1 Q6

With Superpowers 6.4.2, Mellum unnecessarily invoked brainstorming for “Hello” and “Take a look around.” Evidence points to task/workflow routing problems; no internal Mellum defect has been isolated. Remediation: isolate automatic plugins and skills, keep thinking enabled, and retrieve focused snippets; this does not fix every follow-up response.

Date: 2026-10-07. OpenCode 1.18.35; existing Mellum Q6 model and oMLX endpoint.

## Outcome

**OpenCode can run Mellum successfully in a focused workflow.** Its clean profile
completed the three-turn conversation, retrieved all nine exact values from
three approximately 50k source files, and fixed the coding fixture with three
independently passing, unchanged tests. This confirms the practical file-search
workaround in a second agent harness. It does not repair unaided 50k in-context
retrieval or establish that the full historical Superpowers workflow is fixed.

The configured Superpowers run also completed all three conversation answers
after correcting the test's working directory. It unnecessarily invoked
brainstorming on “Hello,” but it did **not** reproduce the unknown-agent loop.
There is no evidence here that switching to OpenCode makes every workflow
reliable, or that Superpowers must always fail with Mellum.

## Method and telemetry

The active database was confirmed by `opencode db path`:

```text
~/.local/share/opencode/opencode.db
```

The additional `storage/opencode.db` file was not used. Analysis opened the
active database with `sqlite3 -readonly` and selected only the newly created
diagnostic sessions and their descendants. No unrelated historical messages,
account records, credentials, or complete database copy were exported.

`message.data` and `part.data` contain JSON projections of messages and tool
states. `session` contains cumulative token totals. The inspected sessions also
have event history in `event`; `session_message` was empty for these sessions.
The [scoped evidence](opencode-evidence.json) includes selected session metadata,
message-level tokens, completed text, reasoning-part summaries, tool inputs and
outputs/errors, and event counts. [inspect_opencode.mjs](inspect_opencode.mjs)
performs this read-only extraction for a runner's newly created sessions.

Actual provider requests were captured through a temporary forwarding proxy to
the existing `127.0.0.1:8001` server. The proxy did not rewrite prompts or sampling
parameters. Published request records contain parameters, tool names, role/size
summaries, content hashes, and response reasoning/usage summaries. Headers and
credentials were not recorded. Bootstrap messages are not published wholesale.

All model requests in these trials selected
`Mellum2.1-12B-A2.5B-Thinking-6bit`. Temporary configuration also selected Mellum
for the build agent and small model, preventing the existing DeepSeek defaults
from becoming a comparison confound. No global configuration was changed.

The diagnostic parent process already disabled Claude-code prompt/skill
sources; the compared runs inherited those flags. Their values and clean-profile
overrides are recorded in the evidence. These are controlled trials of the
installed configuration, not an exact replay of a different shell's bootstrap.

## Controlled conversations

Each conversation used the same sequence: “Hello”; read README and summarize in
up to three sentences; explain the actual actions without tools when challenged
about brainstorming. The corrected runs used the same synthetic README fixture
and explicit `--dir`.

| Profile | Answer/tool outcome | Largest single-response prompt context |
| --- | --- | --- |
| Configured Superpowers, corrected directory | All three substantive answers; brainstorming skill on greeting; glob/read on summary; no tool on challenge | 19,375 tokens |
| Same configuration, **only `--pure` added** | All three substantive answers; no greeting tool; read on summary; no tool on challenge | 9,167 tokens |
| Clean: `--pure`, external skills disabled, restricted tools, temperature 0 | All three substantive answers; glob/read on summary; no tool on challenge; zero tool errors | 6,308 tokens |

The `--pure` comparison isolates removal of external plugins while keeping the
configured model limits and unspecified sampling defaults. The broader clean
profile changes several things and does not isolate each one's causal effect.
Its conversation used the original configured 16,384-token output allowance;
the later retrieval/coding profile explicitly reduced output to 4,096.

Context here means each assistant message's `tokens.input + tokens.cache.read`.
For example, the corrected configured session accumulated 24,129 input and
75,776 cache-read tokens over its responses, but its largest individual prompt
was 19,375. Cumulative processing is not a 99k context window. These figures
describe these trials, not an error-rate or speed benchmark.

## Retrieval and coding

The clean profile used temperature 0, top-p 1, top-k 0, min-p 0, seed 42, and
4,096 output tokens. Captured requests confirm:

```json
"chat_template_kwargs": {
  "enable_thinking": true,
  "preserve_thinking": true
}
```

Files remained on disk. OpenCode retrieved assignment lines using `grep`; the
three fixture files contain start/middle/end values and obsolete decoy files.
The final answer had to equal the one-line golden exactly.

| Fixture | Final answer | Tool errors | Largest prompt context |
| --- | --- | --- | --- |
| 101 | `elm709382 pine988267 ash304214` | 0 | 7,732 |
| 202 | `elm900987 pine504267 ash776101` | 0 | 7,293 |
| 303 | `elm133195 pine351849 ash876428` | 0 | 7,368 |

This is **nine of nine exact literal values**, with all three sessions finishing
with `stop`. The approximately 50k source files were not loaded wholesale into
model context. These trials test agentic retrieval, not raw long-context recall.

The clean coding session read the relevant files, changed the accumulation from
`sum + item.priceCents` to `sum + item.priceCents * item.quantity`, ran the Node
tests, and gave a completed answer. There were zero tool errors; largest prompt
context was 7,719 tokens. An independent test run passed **3/3**, and the test
file matched the original fixture byte-for-byte. The final code and independent
test log are retained in the evidence.

The portable OpenCode retrieval runner and SQLite inspector were separately
executed before packaging; their results are included in the evidence.
The reusable configuration file was also launched independently for a greeting;
captured requests confirmed Mellum, the 4,096-token limit, and enabled thinking.

## Setup issues and misleading success signals

The first configured conversation omitted `--dir`. In this OpenCode release,
the run command consults inherited `PWD`, which still named the real project
despite the child process being started with a temporary `cwd`. The session was
therefore associated with the real project. Mellum invoked brainstorming and
todos on the greeting, then generated a misspelled project path on the README
turn. The headless permission path rejected that external read and the turn
ended without a substantive answer. The CLI still returned exit zero.

That first run is preserved as a **setup-confounded observation**, not the main
paired comparison. After adding explicit `--dir`, the configured fixture
conversation completed all answers. The directory issue is supported both by
SQLite session metadata and the pinned CLI source's use of
`process.env.PWD ?? process.cwd()`.

The first clean retrieval used `/tmp/...` in its explicit search path, while
OpenCode's session directory was canonicalized to `/private/tmp/...`. The
external-directory permission check rejected the first grep. Mellum recovered
by using the working-directory-relative file and returned the exact values.
Repeating with `realpathSync` paths removed that tool error across all three
fixtures. This was a path/permission setup issue; it is not evidence that the
model cannot retrieve the literals.

The rejection text says “The user rejected permission,” but no human rejected
the generated read during these headless trials. Treat it as the harness's
permission outcome, not a recorded user decision.

Two telemetry lessons carry over from Pi:

- **Exit zero is insufficient.** Inspect the final assistant's finish reason,
  substantive text, tool errors, and independently checked task outcome.
- **A zero reasoning-token counter does not mean thinking was disabled.** SQLite
  has reasoning parts, and captured SSE contains `reasoning_content`, while the
  usage counters report zero reasoning tokens. Count this as a usage-accounting
  limitation rather than a no-thinking result.

In this CLI, `--thinking` displays thinking blocks; it is not Pi's thinking-level
switch. Use the model's template options and inspect the actual request/response
to verify thinking mode.

## Recommended OpenCode launch

### Follow-up: “Take a look around”

After the initial report, the user observed another skill invocation on “Take a
look around.” A scoped read of that session confirmed a successful
`skill(brainstorming)` call, followed by a proposed “spike” instead of repository
inspection. The follow-up “Why did you load superpowers?” used `webfetch` on
opencode.ai and answered “To plan next steps.” The normal global configuration
still enabled Superpowers; the clean profile's skill/webfetch restrictions were
not in effect. Selecting Mellum in an existing window does not activate the
separate clean configuration.

A fresh clean-profile trial reproduced those exact prompts against the synthetic
README fixture. “Take a look around” used glob/read, inspected the fixture, and
gave a substantive project summary without invoking a skill. However, the
follow-up fetched opencode.ai via the allowed `bash` tool and answered “To help
with programming tasks,” falsely accepting that it had loaded Superpowers.
Both turns finished with `stop` and zero tool errors, demonstrating that those
signals do not establish correct task interpretation or truthful action reporting.
See [controlled follow-up evidence](opencode-look-around-evidence.json).

This narrows the recommendation: the clean profile isolates skill invocation
and supports focused work; it is not a universal fix for Mellum's task routing
or action explanations. Disabling `webfetch` does not prevent network access
through an allowed shell. A read-only browsing profile could omit shell access,
but that mitigation has not been validated in this follow-up. These results
cannot isolate whether the remaining behavior comes from model limitations,
other instruction sources, or their interaction.

Start a fresh session with the complete launch configuration below. Do not
expect switching models or using `--pure` alone to apply all of its controls.

The [opencode-clean.json](opencode-clean.json) file contains the tested model
limits, explicit thinking options, deterministic sampling, and tool permissions.
It merges with an existing `omlx` provider, preserving its configured credentials.
Global OpenCode configuration, installed packages, and model weights remain
unchanged. From the project you intend to work in:

```bash
OPENCODE_CONFIG=/absolute/path/to/opencode-clean.json \
OPENCODE_DISABLE_EXTERNAL_SKILLS=1 \
OPENCODE_DISABLE_CLAUDE_CODE=1 \
opencode run --pure --dir "$PWD" \
  --model omlx/Mellum2.1-12B-A2.5B-Thinking-6bit \
  --agent build --format json \
  "Search the relevant files, inspect focused snippets, then complete the task."
```

`--pure` disables external plugins such as Superpowers. Disabling external skills
and denying skill/task/todo tools narrows the clean profile further. This does
not promise to disable every OpenCode instruction source: the global OpenCode
`AGENTS.md` can still contribute instructions. No delegated agents were used in
the successful clean tests. The 12-step bound is a diagnostic starting limit;
reaching it is a harness bound, not proof of a model failure.

For a self-contained fixture reproduction:

```bash
node run_opencode.mjs retrieval clean
MELLUM_FIXTURE_SEED=202 node run_opencode.mjs retrieval clean
MELLUM_FIXTURE_SEED=303 node run_opencode.mjs retrieval clean
node run_opencode.mjs coding clean
node run_opencode.mjs conversation pure
node run_opencode.mjs conversation configured
node inspect_opencode.mjs /path/to/the/printed/runDir
```

The runner creates temporary fixture copies and emits `runDir`; the inspector
reads only sessions named in those runner summaries. It produces a sanitized
`evidence.json` there. Check SQLite final finishes/tool errors as well as the
runner's exact retrieval or independent coding-test score. Conversation answers
require semantic review. The runner allows four minutes per turn, explicitly
recorded as a diagnostic bound.

## Assessment and remaining work

**Fact:** clean OpenCode and clean Pi both succeed on the focused retrieval and
small coding checks with the existing Q6 checkpoint. The correct-dir configured
OpenCode conversation also succeeds, despite unnecessary skill use on greeting.

**Inference:** removing plugin bootstrap and narrowing workflow instructions
reduces irrelevant process and context overhead. This is a useful operating
choice, not proof that all historical failures are caused by a plugin.

**Recommendation:** OpenCode is another viable harness for the existing
file-search workaround. Use explicit directories, enable thinking through model
options, keep task context focused, and verify telemetry/task outcomes. There
is no basis here for reconverting weights or claiming OpenCode repairs raw 50k
retrieval. The canonical vLLM comparison and exact historical multi-turn replay
in [handoff.md](handoff.md) remain open.

## Sources

- [OpenCode 1.18.35 run command](https://github.com/anomalyco/opencode/blob/v1.18.35/packages/opencode/src/cli/cmd/run.ts), accessed 2026-10-07; explicit `--dir` and inherited `PWD` resolution.
- [Pinned runtime flags](https://github.com/anomalyco/opencode/blob/v1.18.35/packages/opencode/src/effect/runtime-flags.ts), accessed 2026-10-07; external-skill and Claude-source disabling.
- [Pinned configuration loader](https://github.com/anomalyco/opencode/blob/v1.18.35/packages/opencode/src/config/config.ts), accessed 2026-10-07; explicit/inline configuration merging.
- [OpenCode CLI documentation](https://opencode.ai/docs/cli/), consulted through Context7 and installed `--help`, 2026-10-07; `run`, JSON mode, `--pure`, database path.
- [Scoped experiment evidence](opencode-evidence.json), local experiments, 2026-10-07; source of outcomes and token counts.

No private historical session was replayed. These targeted fixtures are not a
general SWE benchmark, error-rate estimate, or physical 16GB-machine test. The
model filenames and weights are unchanged. The diagnostic forwarding proxy was
stopped after use; the existing oMLX server was preserved.
