"""Turn recorded Pi events into a Score. Pure functions, replayable offline.

Events are the JSON lines written by ``ladder/record-pi.js``:
``provider_request`` (the wire payload), ``tool_call`` (toolName, input),
and ``tool_result`` (toolName, isError, content). Every column maps to a
pathology recorded in ``../local-ai-pi`` or ``../satyrn-evals``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

# A shell redirect or tee that writes a file. Stream-merge forms such as
# ``2>&1`` and ``>/dev/null`` are stripped first so they do not count.
_NOISE = re.compile(r"\d?>&\d|&?>\s*/dev/null")
_MUTATION = re.compile(r">{1,2}\s*\S|\btee\b|<<-?\s*['\"]?\w")


def bash_mutates(command: str) -> bool:
    """True when a bash command writes a file through a redirect, tee, or heredoc."""
    return bool(_MUTATION.search(_NOISE.sub("", command)))


def call_key(name: str, payload: object) -> str:
    """Stable identity for a tool call: same tool and same arguments, any key order."""
    return name + "\0" + json.dumps(payload, sort_keys=True, default=str)


@dataclass
class Score:
    requests: int = 0
    largest_prompt_chars: int = 0
    tool_calls_by_name: dict[str, int] = field(default_factory=dict)
    tool_errors: int = 0
    edit_anchor_failures: int = 0
    noop_edits: int = 0
    write_existing: list[dict] = field(default_factory=list)
    bash_file_mutations: int = 0
    max_identical_streak: int = 0
    write_shrink: int = 0
    nudges: int = 0

    def as_row(self) -> dict:
        row = asdict(self)
        row["write_existing"] = len(self.write_existing)
        return row


def _path(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("path", "filePath", "file_path"):
        if key in payload:
            return str(payload[key])
    return None


def score(events: list[dict], baseline_paths: set[str], baseline_lines: dict[str, int]) -> Score:
    result = Score()
    streak = 0
    last_key = None
    for event in events:
        kind = event.get("type")
        if kind == "provider_request":
            result.requests += 1
            payload = event.get("payload", {})
            size = len(json.dumps(payload))
            result.largest_prompt_chars = max(result.largest_prompt_chars, size)
            nudges = sum(
                "[mellum-guard]" in str(m.get("content", ""))
                for m in (payload.get("messages") or [])
                if isinstance(m, dict)
            )
            result.nudges = max(result.nudges, nudges)
        elif kind == "tool_call":
            name = event["toolName"]
            payload = event.get("input", {})
            result.tool_calls_by_name[name] = result.tool_calls_by_name.get(name, 0) + 1
            key = call_key(name, payload)
            streak = streak + 1 if key == last_key else 1
            last_key = key
            result.max_identical_streak = max(result.max_identical_streak, streak)
            if name == "write":
                path = _path(payload)
                if path and path in baseline_paths:
                    content = str(payload.get("content", ""))
                    before = baseline_lines.get(path, 0)
                    after = len(content.splitlines())
                    result.write_existing.append(
                        {"path": path, "lines_before": before, "lines_after": after}
                    )
                    if after < before:
                        result.write_shrink += 1
            if name == "bash" and bash_mutates(str(payload.get("command", ""))):
                result.bash_file_mutations += 1
        elif kind == "tool_result":
            content = str(event.get("content", ""))
            if event.get("isError"):
                result.tool_errors += 1
            if event["toolName"] == "edit":
                if "not found" in content or "oldString" in content or "Could not find" in content:
                    result.edit_anchor_failures += 1
                if "No changes made" in content:
                    result.noop_edits += 1
    return result
