# Ladder fixtures

Each directory is one rung of the prompt ladder: a small project whose own
tests are the pass check. Rungs 1, 4, and 5 start with failing tests on
purpose; rungs 2 and 3 start green.

**Do not run the worker against these directories.** It edits files in place
and the baseline stops being a baseline. Get a disposable copy instead:

```bash
uv run python -m ladder.sandbox 1
```

That prints a scratch path with the fixture copied and committed; start Pi
there. The ladder runner (`ladder/run_ladder.py`) always works on copies.

| Rung | Directory | Sentence |
| --- | --- | --- |
| 1 | `calculator/` | the cart total ignores quantity, fix it |
| 2 | `ledger/` | add a balance() that sums the entries, with a test |
| 3 | `rename/` | rename fetch_rows to load_rows everywhere |
| 4 | `feature/` | make the failing test pass |
| 5 | `edge/` | the export is missing the totals row |
