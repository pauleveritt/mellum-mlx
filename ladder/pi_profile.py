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

from .omlx_profiles import REQUEST_PARAMS

ROOT = Path(__file__).resolve().parent.parent
MODEL_ID = "Mellum2.1-12B-A2.5B-Thinking-6bit"
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
    (dest / "trust.json").write_text(
        json.dumps({str(p): True for p in trusted}, indent=2)
    )
    return dest


def prepare_pi_workspace(ws: Path, record_ext: Path) -> Path:
    """Give a scratch workspace the worker definition with the ladder recorder appended."""
    pi = ws / ".pi"
    (pi / "agents").mkdir(parents=True, exist_ok=True)
    (pi / "mellum").mkdir(exist_ok=True)
    shutil.copy2(
        ROOT / ".pi" / "mellum" / "mellum-guards.ts",
        pi / "mellum" / "mellum-guards.ts",
    )
    lines = (
        (ROOT / ".pi" / "agents" / "mellum-worker.md")
        .read_text()
        .splitlines(keepends=True)
    )
    rewritten = [
        f"subagentOnlyExtensions: ./.pi/mellum/mellum-guards.ts, {record_ext}\n"
        if line.startswith("subagentOnlyExtensions:")
        else line
        for line in lines
    ]
    (pi / "agents" / "mellum-worker.md").write_text("".join(rewritten))
    return pi


def direct_agent_dir(
    dest: Path, profile: str, base_url: str = "http://127.0.0.1:8001/v1"
) -> Path:
    """A minimal Pi agent directory whose omlx model entry sends the profile's request values.

    Direct mode uses this instead of the operator's profile so that temperature,
    caps, and penalties are the ladder's, not Pi's defaults.
    """
    request = dict(REQUEST_PARAMS[profile])
    max_tokens = request.pop("max_tokens")
    entry = {
        "id": MODEL_ID,
        "name": "Mellum ladder",
        "reasoning": True,
        "input": ["text"],
        "contextWindow": 56000,
        "maxTokens": max_tokens,
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        "compat": {
            "supportsDeveloperRole": False,
            "supportsReasoningEffort": False,
            "maxTokensField": "max_tokens",
            "thinkingFormat": "qwen-chat-template",
        },
        "samplingParams": request,
    }
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "models.json").write_text(
        json.dumps(
            {
                "providers": {
                    "omlx": {
                        "baseUrl": base_url,
                        "api": "openai-completions",
                        "apiKey": "not-needed",
                        "models": [entry],
                    }
                }
            },
            indent=2,
        )
    )
    (dest / "settings.json").write_text(
        json.dumps(
            {
                "defaultProvider": "omlx",
                "defaultModel": MODEL_ID,
                "defaultThinkingLevel": "high",
                "compaction": {"enabled": False},
                "quietStartup": True,
            },
            indent=2,
        )
    )
    return dest
