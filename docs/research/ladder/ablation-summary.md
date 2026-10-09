# Lean-down ablation: summary

Date: 2026-10-08/09. Plan: [2026-10-09-mellum-worker-lean-ablation.md](../../superpowers/plans/2026-10-09-mellum-worker-lean-ablation.md).
Reference: phase 2b, 15/15, measured again as A0 in the form that ships.
Rule: a removal stands when passes are within one of the reference and no
scorer column that was zero becomes non-zero.

| step | removed | passes | kept? | why |
| --- | --- | --- | --- | --- |
| [A0](ablation-a0-replace/README.md) | Pi's base prompt under the worker prompt (measures `replace`, what ships) | 15/15 | reference | fewer requests, errors, nudges than append |
| [A1](ablation-a1-noguards/README.md) | the guard extension | 13/15 | no | both failures are the empty turn the nudge answers |
| [A2](ablation-a2-v4a/README.md) | the six-step procedure block | 15/15 | **yes → prompt v4** | cleanest phase of the night: 12.3 requests/run, no anchor failure, no nudge |
| [A3](ablation-a3-v4b/README.md) | the five tool facts | 15/15 | **yes → prompt v5** (after the review) | first reverted on `loop_breaker_would_block` 0 → 2; the review showed that column came from a breaker that counted re-reads after an edit as repeats — corrected, the replay refuses nothing anywhere, and A3 holds under the rule |
| [A4](ablation-a4-v4c/README.md) | the missing-files line (facts only) | 14/15 | no | the failure edited a test to pass |
| [A5](ablation-a5-thinking-medium/README.md) | thinking high → medium | 15/15 | n/a | the level never reaches oMLX; A5 is A2 repeated, and sets the noise floor |
| A6 | `allowedAgents`, `defaultContext`, `thinking` lines | — | yes | redundant under pi-subagents defaults, or inert |
| A6 | `excludeTools: contact_supervisor` | — | **no** | A8: pi-subagents injects the tool regardless of the allowlist |
| A7 | the parent-side skill | — | yes | read 2/15, 15/15 either way (phase 3b) |
| [A8](ablation-a8-delegated-lean/README.md) | (delegated check, before the `excludeTools` fix) | 14/15 | — | supervisor tool present; one async parent launch |
| [A9](ablation-a9-delegated-final/README.md) | (delegated check, prompt v4) | 14/15 | — | the one failure is an empty child turn the parent reported honestly |
| [A10](ablation-a10-delegated-v5/README.md) | (delegated check, prompt v5, as shipped) | 15/15 | ships | no re-dispatch, no empty child turn |

## The worker, before and after

| | before (phase 3) | after |
| --- | --- | --- |
| prompt | v3, 1,569 chars, five tool facts + six test facts + six procedure steps | v5, 643 chars: the six test-command facts and the missing-files line |
| agent frontmatter | 17 lines | 13 lines |
| guards on | nudge cap 1 (experimental), in `.pi/extensions/` (auto-loaded into the parent too) | nudge cap 3 + loop breaker (measured 15/15), in `.pi/mellum/`, child only |
| parent-side skill | 45 lines, read 2/15 | none |
| direct mode, 15 runs | 15/15 sampled; 13–14/15 greedy | 15/15 (A3 = v5); v4 15/15 twice (A2, A5) |
| delegated, 15 runs | 15/15 | 15/15 (A10, v5) |

## The review's correction

The fresh whole-branch review found the loop breaker treated a re-read
after an edit as a repeat, and that it had refused one such read in two
passing runs (A9 rung 2 r1, A3 rung 4 r2). The breaker now forgets
repeats after any edit, write, or bash call; the scorer's replay matches;
every phase was rescored. `loop_breaker_would_block` is zero in all 330
runs, which removed the only evidence against A3.

## What the pass did not remove, and why

- **The missing-files line.** A4's one failure edited a test; with it
  (A3) no run did. One line, kept.
- **The guard extension's dormant guards** (new-file-only `write`, step
  budget) are code that never ran in 300 runs. They stay because removing
  them is not a measurement; backlog.
- **Server-profile switching in `ladder/omlx_profiles.py`.** The knobs it
  switches are inert (1c/1d); the records cite it. Backlog.

## Open

1. **The nudge does not fire inside pi-subagents children** (A9): the
   parent's re-dispatch recovers the empty turn instead, 10 of 11 times.
   Either make the hook work under pi-subagents or put "re-dispatch once on
   'produced no output'" in the worker's advertised description, which the
   parent reads unconditionally.
2. pi-subagents appends its "Intercom orchestration channel" block to the
   child prompt even with the tool excluded; ~2,000 characters the worker
   does not use.
3. One parent launched the child asynchronously and ended its turn (A8).
