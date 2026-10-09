---
name: delegate-to-mellum
description: Use when handing a coding task to the mellum-worker subagent (a small local model). Scope the task first, send a brief in the fixed template, then verify the result yourself.
---

# Delegate to mellum-worker

mellum-worker is a 12B local model with file tools. It completes bounded
tasks reliably when the brief names the files, the change, and the test
command; it stalls or stops silently on tasks it has to scope itself.

## Before dispatching: scope the task yourself

1. Find the files: `grep -rn <identifier>` or `find` for the names in the
   request. Open them. Name every file the change touches.
2. Name the test command and run it once to see the current failure
   (`uv run pytest -q`, `node --test <file>`, or whatever the project uses).
3. Write the acceptance criterion as the test command exiting 0 plus any
   file that must not change.

## The brief

Send exactly this shape as the `task`:

```
Files: <paths, one per line, relative to the working directory>
Change: <what to change in each file, in one or two sentences each>
Test command: <the exact command, run from <directory>>
Do not change: <files that must stay as they are, or "nothing else">
Done when: the test command exits 0 and you have replied with the files changed and the test output.
```

Do not send the user's sentence as the task. Do not ask the worker to
explore, choose an approach, or decide scope.

## After the worker returns

1. Run the test command yourself. The worker's report is not the result;
   the test exit code is.
2. If the worker's reply is empty, or the tests fail, re-dispatch **once**
   with the same brief plus the failing test output pasted under
   `Current failure:`. A second empty reply means the task is beyond it:
   do the remaining change yourself and say so.
3. Report to the user: files changed, test output, and whether the worker
   or you made the final change.
