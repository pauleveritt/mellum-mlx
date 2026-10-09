# Future work, scheduled

Date: 2026-10-09. What ships today: **Mellum Worker** (the `mellum-worker` subagent,
`.pi/agents/mellum-worker.md`, prompt v5, guards at `.pi/mellum/`) and
**Mellum Mode** (`/mellum <task>` and `on|off`, `.pi/mellum/mellum-mode.ts`), both measured 14–15/15 on
the ladder; the recipe in `docs/mellum-worker.md`. Everything below is
unmeasured or measured once, with what it would cost to settle.

| # | item | why | cost to measure | records |
| --- | --- | --- | --- | --- |
| 1 | Make the nudge fire inside pi-subagents children, or write "re-dispatch once on 'produced no output'" into the worker's advertised description | the child's one pathology; the parent recovers it 12/13 times unprompted today | a probe of pi-subagents' hook forwarding, then one delegated phase (15 runs, ~20 min) | A9, A11 |
| 2 | ~~Handoff collapse after `/mellum off`~~ done 2026-10-09: the `context` hook sends the parent one block per finished span (task, files, last command output, final reply); the probe's parent request went from 18 messages to 3 | — | — | A14 |
| 3 | `async: false` in the worker's frontmatter | prevents the one async-launch failure | one delegated phase | A8 |
| 4 | The "no steps" brief shape (files, change, test command, done-when) as one prompt | A16 measured a brief with intermediate replies, which the model obeyed; the shape itself is untested | the brief files and one phase (15 runs) | A15/A16 |
| 5 | Verification between chunk steps | the verify loop from the `pi-circuitbreaker` notes; chunking alone cost 2.4× | runner change plus one phase | A15 |
| 6 | A fixture with an uncommon directory name and a plan document in it (the "sedgewick → swaggers" report), plus an unseen-path guard | the worker has never been measured on path regeneration; 350 runs had zero wrong-path edits on plain names | one fixture, one scorer column, one guard, one phase | — |
| 7 | Serve Mellum with a reasoning parser on oMLX so `thinking_budget` is enforced; then measure the budget hook at medium | the only remaining lever on thinking cost; A13 showed the hook works and the server ignores it | server configuration, then one phase | A13 |
| 8 | In-process child through Pi's SDK (`createAgentSession`) as a tool | removes pi-subagents' 521-char preamble and makes the nudge ours; only matters if the parent round trip stays | ~200 lines, one delegated phase | A9 |
| 9 | OpenCode port of Mellum Worker (phase 4 of the original plan; OpenCode has no payload hook, so Mellum Mode has no counterpart there and Mellum Worker is the name) | the global `mellum-worker` block in `~/.config/opencode/opencode.jsonc` is unmeasured | the ladder's `--harness opencode` and one phase | — |
| 11 | ~~Exercise `/mellum` interactively~~ done 2026-10-09 (`ladder/probe_mode_rpc.py`); still open: whether the nudge fires during an interactive turn, and the compaction refusal under a real threshold | the probe showed prompt, history, tools and restore correct in every step | re-run the probe with a long parent history | A14 |
| 10 | Ladder tooling: remove server-profile switching (`ladder/omlx_profiles.py` PUT path) and the dormant guards; run-dir names that carry prompt/mode/thinking | measured inert (1c/1d) and never exercised | an afternoon, no phase | 1c/1d, A1 |

Not scheduled, with reason: stripping prior-turn thinking (A12: 60% slower);
a request-level thinking budget without a reasoning parser (A13: inert);
Pi's thinking level (A5: never reaches oMLX); a parent-side skill (3b: read
2/15); chunked briefs as measured (A15: 2.4× cost).
