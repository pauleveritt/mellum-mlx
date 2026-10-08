"""Hand out a disposable, git-initialised copy of a ladder fixture for interactive tries.

    uv run python -m ladder.sandbox 1        # prints the scratch path for rung 1

Never point the worker at ``fixtures/`` itself: it edits files in place and
the ladder's "known-buggy baseline" stops being buggy.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from .run_ladder import ROOT, prepare_workspace
from .rungs import RUNGS


def make_sandbox(rung: int, parent: Path | None = None) -> Path:
    scratch = Path(tempfile.mkdtemp(prefix=f"mellum-try-rung{rung}-", dir=parent))
    ws = prepare_workspace(RUNGS[rung], scratch)
    # pi-subagents finds project agents from the nearest .pi/, so carry ours along.
    shutil.copytree(ROOT / ".pi", ws / ".pi", ignore=shutil.ignore_patterns("*.test.mjs"))
    return ws


if __name__ == "__main__":
    number = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    ws = make_sandbox(number)
    print(ws)
    print(f'try: cd {ws} && pi   # then: "Use mellum-worker: {RUNGS[number].sentence}"')
