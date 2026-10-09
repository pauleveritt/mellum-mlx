"""A temporary Pi agent directory mirroring the operator's, and the ladder's workspace `.pi/`.

Delegated runs launch the parent with ``PI_CODING_AGENT_DIR`` pointing at the
mirror, so the parent has its normal settings, models, credentials, and
packages while nothing under ``~/.pi/agent`` is written to. The scratch
workspace gets a copy of the committed worker definition with the ladder's
recorder appended, because pi-subagents overrides cannot add extensions.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COPIED_FILES = ("settings.json", "models.json", "auth.json", "AGENTS.md")
LINKED_DIRS = ("git", "npm")


def mirror_agent_dir(source: Path, dest: Path, trusted: list[Path]) -> Path:
    """Copy the parent's configuration, link its packages, trust the given workspaces."""
    dest.mkdir(parents=True, exist_ok=True)
    for name in COPIED_FILES:
        if (source / name).exists():
            shutil.copy2(source / name, dest / name)
    if (source / "extensions").is_dir():
        shutil.copytree(source / "extensions", dest / "extensions", dirs_exist_ok=True)
    for name in LINKED_DIRS:
        if (source / name).exists():
            os.symlink(source / name, dest / name, target_is_directory=True)
    (dest / "trust.json").write_text(json.dumps({str(p): True for p in trusted}, indent=2))
    return dest


def prepare_pi_workspace(ws: Path, record_ext: Path, skill: bool) -> Path:
    """Give a scratch workspace the worker definition with the ladder recorder, and optionally the skill."""
    pi = ws / ".pi"
    (pi / "agents").mkdir(parents=True, exist_ok=True)
    (pi / "extensions").mkdir(exist_ok=True)
    shutil.copy2(ROOT / ".pi" / "extensions" / "mellum-guards.ts", pi / "extensions" / "mellum-guards.ts")
    lines = (ROOT / ".pi" / "agents" / "mellum-worker.md").read_text().splitlines(keepends=True)
    rewritten = [
        f"subagentOnlyExtensions: ./.pi/extensions/mellum-guards.ts, {record_ext}\n"
        if line.startswith("subagentOnlyExtensions:")
        else line
        for line in lines
    ]
    (pi / "agents" / "mellum-worker.md").write_text("".join(rewritten))
    if skill:
        shutil.copytree(ROOT / ".pi" / "skills" / "delegate-to-mellum", pi / "skills" / "delegate-to-mellum")
    return pi
