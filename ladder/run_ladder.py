"""Run ladder rungs against the Mellum worker and score the evidence.

Direct mode launches ``pi -p`` in the recovery report's clean profile: no
extensions, skills, or context files; the worker prompt appended; the
bundle's record extension capturing every provider request and tool event.

    uv run python -m ladder.run_ladder --profile baseline --rung 1 --repeat 3 --out docs/research/ladder/phase0-baseline
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from .omlx_profiles import AdminClient, profile
from .rungs import FIXTURES, RUNGS, Rung, copy_fixture
from .score import score

ROOT = Path(__file__).resolve().parent.parent
PROMPT_FILE = ROOT / "prompts" / "mellum-worker.md"
RECORD_EXT = ROOT / "ladder" / "record-pi.js"
GUARDS_EXT = ROOT / ".pi" / "extensions" / "mellum-guards.ts"
MODEL = "omlx/Mellum2.1-12B-A2.5B-Thinking-6bit"
MODEL_ID = MODEL.split("/", 1)[1]
TOOLS = "read,grep,find,ls,bash,edit,write"
PROMPT_VERSION = "v2"

HEADER = (
    "| rung | profile | mode | rep | result | tests_unchanged | requests | tool_errors | anchor_fail | "
    "noop_edit | write_existing | bash_mut | max_streak | largest_prompt_chars | deadline | wall_s (untrusted) |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
)


def build_pi_direct_args(trace: Path, sentence: str, guards: bool = False) -> list[str]:
    args = [
        "pi", "-p", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes",
        "--no-context-files", "--no-session", "--thinking", "high", "--model", MODEL,
        "--tools", TOOLS, "--append-system-prompt", str(PROMPT_FILE), "-e", str(RECORD_EXT),
    ]
    if guards:
        args += ["-e", str(GUARDS_EXT)]
    return [*args, sentence]


def git(ws: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=ws, capture_output=True, text=True).stdout


def prepare_workspace(rung: Rung, scratch: Path) -> Path:
    ws = copy_fixture(rung.fixture, scratch / f"rung{rung.number}")
    git(ws, "init", "-q")
    git(ws, "add", "-A")
    git(ws, "-c", "user.name=ladder", "-c", "user.email=ladder@localhost", "commit", "-qm", "baseline")
    if (ws / "pyproject.toml").exists():
        subprocess.run(["uv", "sync", "--offline"], cwd=ws, capture_output=True)
    return ws


def baseline_index(ws: Path) -> tuple[set[str], dict[str, int]]:
    paths = {p for p in git(ws, "ls-files").split() if p}
    lines = {p: len((ws / p).read_text(errors="replace").splitlines()) for p in paths}
    return paths, lines


def read_events(trace: Path) -> list[dict]:
    if not trace.exists():
        return []
    return [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]


def run_once(rung: Rung, mode: str, prof: str, repeat: int, out: Path, deadline: int,
             versions: dict, guards: bool) -> dict:
    scratch = Path(tempfile.mkdtemp(prefix="ladder-"))
    ws = prepare_workspace(rung, scratch)
    paths, lines = baseline_index(ws)
    trace = scratch / "trace.jsonl"
    env = {**os.environ, "MELLUM_TRACE_FILE": str(trace), "PI_OFFLINE": "1"}
    args = build_pi_direct_args(trace, rung.sentence, guards)
    started = time.time()
    deadline_hit = False
    stdout = ""
    try:
        proc = subprocess.run(args, cwd=ws, env=env, capture_output=True, text=True, timeout=deadline)
        stdout = proc.stdout + ("\n[stderr]\n" + proc.stderr if proc.stderr else "")
    except subprocess.TimeoutExpired as error:
        deadline_hit = True
        captured = error.stdout or b""
        stdout = captured.decode(errors="replace") if isinstance(captured, bytes) else str(captured)
    wall = time.time() - started
    events = read_events(trace)
    git(ws, "add", "-A")
    record = {
        "rung": rung.number,
        "repeat": repeat,
        "profile": prof,
        "mode": mode,
        "harness": "pi",
        "guards": guards,
        "prompt_version": PROMPT_VERSION,
        "versions": versions,
        "sentence": rung.sentence,
        "started": started,
        "wall_seconds_untrusted": round(wall, 1),
        "deadline_hit": deadline_hit,
        "check": asdict(rung.check(ws, FIXTURES / rung.fixture)),
        "score": score(events, paths, lines).as_row(),
        "diff_stat": git(ws, "diff", "--cached", "--stat"),
        "files_created": [p for p in git(ws, "diff", "--cached", "--name-only", "--diff-filter=A").split() if p],
        "workspace": str(ws),
    }
    run_dir = out / f"rung{rung.number}-{prof}-{mode}{'-guards' if guards else ''}-r{repeat}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(record, indent=2, default=str))
    if trace.exists():
        shutil.copy(trace, run_dir / "trace.jsonl")
    (run_dir / "stdout.txt").write_text(stdout)
    (run_dir / "diff.patch").write_text(git(ws, "diff", "--cached"))
    return record


def table_row(record: dict) -> str:
    s, c = record["score"], record["check"]
    result = "pass" if c["passed"] else "FAIL"
    return (
        f"| {record['rung']} | {record['profile']}{'+guards' if record['guards'] else ''} | {record['mode']} | "
        f"{record['repeat']} | {result} | {c['tests_unchanged']} | {s['requests']} | {s['tool_errors']} | "
        f"{s['edit_anchor_failures']} | {s['noop_edits']} | {s['write_existing']} | {s['bash_file_mutations']} | "
        f"{s['max_identical_streak']} | {s['largest_prompt_chars']} | {record['deadline_hit']} | "
        f"{record['wall_seconds_untrusted']} |\n"
    )


def tool_version(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", choices=["pi"], default="pi")
    parser.add_argument("--mode", choices=["direct"], default="direct")
    parser.add_argument("--profile", choices=["baseline", "tuned"], required=True)
    parser.add_argument("--rung", type=int, action="append", required=True)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--deadline", type=int, default=600)
    parser.add_argument("--guards", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--omlx", default="http://127.0.0.1:8001")
    args = parser.parse_args(argv)

    client = AdminClient(args.omlx)
    versions = {"pi": tool_version(["pi", "--version"]), "omlx": tool_version(["omlx", "--version"])}
    args.out.mkdir(parents=True, exist_ok=True)
    table = args.out / "table.md"
    if not table.exists():
        table.write_text(HEADER)
    settings_path = Path.home() / ".omlx" / "model_settings.json"
    with profile(client, MODEL_ID, args.profile, settings_path) as live:
        versions["model_settings"] = {
            k: live.get(k) for k in ("max_tokens", "thinking_budget_tokens", "presence_penalty", "max_tool_result_tokens")
        }
        for number in args.rung:
            for repeat in range(1, args.repeat + 1):
                record = run_once(RUNGS[number], args.mode, args.profile, repeat, args.out, args.deadline, versions, args.guards)
                row = table_row(record)
                with table.open("a") as stream:
                    stream.write(row)
                print(row, end="", flush=True)


if __name__ == "__main__":
    main()
