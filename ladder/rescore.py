"""Recompute the ``score`` block of every run.json in a directory from its trace.

The baseline line counts come from ``baseline_lines`` in run.json; runs
recorded before that field existed fall back to the still-present workspace.

    uv run python -m ladder.rescore docs/research/ladder/phase0-baseline
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .run_ladder import HEADER, read_events, table_row
from .score import score


def baseline_from_workspace(ws: Path) -> dict[str, int]:
    out = subprocess.run(["git", "ls-files"], cwd=ws, capture_output=True, text=True).stdout
    return {p: len((ws / p).read_text(errors="replace").splitlines()) for p in out.split() if p}


def rescore_dir(directory: Path) -> int:
    changed = 0
    rows = []
    for run_json in sorted(Path(directory).glob("*/run.json")):
        record = json.loads(run_json.read_text())
        lines = record.get("baseline_lines")
        if lines is None:
            ws = Path(record.get("workspace", ""))
            if not ws.exists():
                continue
            lines = baseline_from_workspace(ws)
            record["baseline_lines"] = lines
        new = score(read_events(run_json.with_name("trace.jsonl")), set(lines), lines).as_row()
        if new != record.get("score"):
            record["score"] = new
            changed += 1
        run_json.write_text(json.dumps(record, indent=2, default=str))
        if "check" in record and "stop_reason" in record:
            rows.append((record["rung"], record["repeat"], table_row(record)))
    if rows:
        Path(directory, "table.md").write_text(HEADER + "".join(r for _, _, r in sorted(rows)))
    return changed


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(f"{arg}: {rescore_dir(Path(arg))} run.json files rescored")
