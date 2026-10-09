# Mellum worker: lean-down ablation plan

**Goal:** finish with the smallest worker that holds the measured pass rate.
Remove one part at a time, re-measure on the ladder, keep the removal only
when the ladder holds.

**Reference set:** phase 2b's configuration, 15/15: direct mode, greedy,
`tuned` request parameters (cap 16,384, presence penalty 0.5 — kept so that
only one thing changes per step; 1c/1d showed the penalty is inert), prompt
v3, guards with the nudge capped at 3 and the loop breaker live. Every step
is measured with the same command shape:

```bash
MELLUM_GUARDS='{"emptyFinalNudge":3,"loopBreaker":true}' uv run python -m ladder.run_ladder --mode direct --guards --profile tuned --prompt-mode replace --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --deadline 600 --out docs/research/ladder/ablation-<step>
```

**Regression rule:** a removal stands when the pass count is within one of
the reference and no scorer column that was zero becomes non-zero. Otherwise
revert it and go on to the next part. Three repeats are a gate, not an error
rate; a removal that lands exactly one short gets one more 15-run repeat
before it is reverted.

## Step A0: measure what ships

Direct mode so far appended v3 under Pi's base prompt (`--append-system-prompt`),
while the shipped agent file uses `systemPromptMode: replace`. Phases 0–2
measured a prompt the subagent never sees. A0 is v3 alone, replace mode, and
is the reference for every step below. If A0 is worse than append mode, the
agent file switches to `systemPromptMode: append` and that is the finding.

## Step A1: no guards extension

`subagentOnlyExtensions` empty; `--guards` off. Dormant guards
(new-file-only write, loop breaker, step budget) were never exercised in
135 direct runs. The nudge is the only one with evidence either way; 2b
decides whether it stays. If A1 holds, the extension and its test are
deleted.

## Step A2: prompt v4a — no procedure block

`prompts/ablation/v4a-no-procedure.md`: the six-step procedure removed, the
retry step kept as a fact under the test command. Steps 1–4 and 6 are
rules of conduct, which the recorded pathologies say the model ignores or
over-follows.

## Step A3: prompt v4b — no tool descriptions

`prompts/ablation/v4b-no-procedure-no-tools.md`: Pi's own tool schemas
already say what each tool does. The one line that might be load-bearing
is the `edit` byte-for-byte fact (anchor failures are a recorded column).

## Step A4: prompt v4c — completion facts only

`prompts/ablation/v4c-completion-facts-only.md`: the test-command block
alone. If this holds, the worker prompt is nine lines.

## Step A5: thinking level

`--thinking medium`, then `low`, on the leanest prompt that held. Thinking
tokens are the cost of every request; the 1c `length` stop was 4,096
tokens of thinking.

## Step A6: agent-file frontmatter (judged, then one delegated run)

Lines whose removal cannot be measured in direct mode. Each is removed if
pi-subagents' default already gives the same behaviour, and the result is
confirmed by one 15-run delegated phase:

- `excludeTools: contact_supervisor` — **removed, then restored by A8.** The
  docs read as if it only narrows the `tools` allowlist; the delegated run
  showed pi-subagents injects `contact_supervisor` and a supervisor-protocol
  prompt block into every child regardless, and two children called it.
- `thinking: high` — removed after A5 showed the level never reaches oMLX.
- `allowedAgents:` empty — removed. "An empty list denies every descendant
  launch. This only narrows an existing nesting grant": the worker has no
  `subagent` tool and no `allowNestedSubagents`, so there is nothing to narrow.
- `defaultContext: fresh` — removed. The documented fallback without a global
  `defaultSubagentContext` is `fresh`, and the operator profile sets none.
  Cost if wrong: an operator who later sets a global `fork` default gets a
  forked worker; noted in the README.
- `advertise: true` — stays; it is how the parent sees the worker.
- `acceptance:` block — stays; the measured failure mode is recorded.
- `inheritProjectContext/GlobalContext/Skills: false` — stay; cheap, and they
  are the recovery report's remedy, not something the ladder measures.

## Step A7: the parent-side skill

`.pi/skills/delegate-to-mellum/SKILL.md` was read in 2 of 15 runs and the
pass rate was 15/15 either way (phase 3b). No run needed: it is removed and
its content becomes a paragraph in the README.

## Step A8: ladder tooling

Not the worker, but measured along the way: server-profile switching in
`ladder/omlx_profiles.py` exists to test knobs that 1c/1d showed do not
matter. It stays this night (the records cite it) and is listed for removal
in the backlog.

## Record

One `docs/research/ladder/ablation-<step>/README.md` per step with the
pass table against the reference, and a closing
`docs/research/ladder/ablation-summary.md` with the kept/reverted list and
the final worker.
