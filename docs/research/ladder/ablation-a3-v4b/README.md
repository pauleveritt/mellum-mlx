# Ablation A3: prompt v4b — no tool descriptions

Date: 2026-10-08. [A2](../ablation-a2-v4a/README.md) with
`prompts/ablation/v4b-no-procedure-no-tools.md`: the five "tools, stated
exactly" lines removed as well, on the argument that Pi's tool schemas
already say what each tool does. 643 characters.

```bash
MELLUM_GUARDS='{"emptyFinalNudge":3,"loopBreaker":true}' uv run python -m ladder.run_ladder --mode direct --guards --profile tuned --prompt-mode replace --prompt prompts/ablation/v4b-no-procedure-no-tools.md --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --deadline 600 --out docs/research/ladder/ablation-a3-v4b
```

| rung | A2 (v4a) | A3 (v4b) |
| --- | --- | --- |
| 1–5 | 15/15 | 15/15 |

| measure (15 runs) | A2 | A3 |
| --- | --- | --- |
| requests per run, mean / max | 12.3 / 19 | 14.3 / 27 |
| tool errors / anchor failures | 11 / 0 | 17 / 3 |
| nudges | 0 | 2 |
| `loop_breaker_would_block` | 0 | **2** (rung 4 r2: `export.py` read seven times in a window of twenty) |

Passes hold, but a column that was zero in the reference went non-zero:
rung 4 r2 re-read the same file seven times, took 27 requests and two
nudges, and the loop breaker's exact replay would have refused two calls.
Anchor failures returned (0 → 3), which is the one tool fact with a
plausible mechanism: "the old text must match the file byte for byte".

**Reverted under the regression rule** (no zero column may go non-zero).
The tool facts cost 490 characters and appear to buy fewer re-reads and
cleaner edits. The pass count alone would have kept it; the rule is there
for exactly this case.
