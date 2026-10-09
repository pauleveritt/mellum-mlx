# Ablation A4: prompt v4c — the test-command facts only

Date: 2026-10-08. [A3](../ablation-a3-v4b/README.md) with
`prompts/ablation/v4c-completion-facts-only.md`: also without "if the
files for the task cannot be found, reply with what is missing and stop".
556 characters: one line of role, six facts about the test command.

```bash
MELLUM_GUARDS='{"emptyFinalNudge":3,"loopBreaker":true}' uv run python -m ladder.run_ladder --mode direct --guards --profile tuned --prompt-mode replace --prompt prompts/ablation/v4c-completion-facts-only.md --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --deadline 600 --out docs/research/ladder/ablation-a4-v4c
```

| rung | A2 (v4a) | A4 (v4c) |
| --- | --- | --- |
| 1–4 | 12/12 | 12/12 |
| 5 | 3/3 | 2/3 |

The one failure (rung 5 r1) is the worst kind: the model edited
`test_export.py` so that "3 passed" came out, and reported success. The
check fails any run that changes a test. This is the only test edit by
the worker in 229 direct runs; bare Pi did it once in fifteen.

**Reverted**, and moot in any case because A3 was reverted: v4c is a
subset of v4b. Noted for the record: with only the completion facts, the
worker's path to "exit 0" once ran through the test file. v4a's tool facts
and missing-files line stand between the model and that shortcut, or three
repeats were kind; either way the lean prompt is v4a.
