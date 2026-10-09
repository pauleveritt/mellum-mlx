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
import re
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from .omlx_profiles import PROFILES, AdminClient, check_effective_params, profile
from .pi_profile import direct_agent_dir, mirror_agent_dir, prepare_pi_workspace
from .rungs import FIXTURES, RUNGS, Rung, copy_fixture
from .score import score

ROOT = Path(__file__).resolve().parent.parent
PROMPT_FILE = ROOT / "prompts" / "mellum-worker.md"
RECORD_EXT = ROOT / "ladder" / "record-pi.js"
GUARDS_EXT = ROOT / ".pi" / "mellum" / "mellum-guards.ts"
MODEL = "omlx/Mellum2.1-12B-A2.5B-Thinking-6bit"
MODEL_ID = MODEL.split("/", 1)[1]
TOOLS = "read,grep,find,ls,bash,edit,write"


def prompt_version(prompt: Path) -> str:
    """The version named in the prompt file's first-line marker, else its stem."""
    first = prompt.read_text().splitlines()[0] if prompt.exists() else ""
    found = re.search(r"prompt (v\w+)", first)
    return found.group(1) if found else prompt.stem


PARENT_PROMPT = "Use mellum-worker to do this: {sentence}"

HEADER = (
    "| rung | profile | mode | rep | result | tests_unchanged | requests | tool_errors | anchor_fail | "
    "noop_edit | write_existing | write_shrink | bash_mut | max_streak | largest_prompt_chars | nudges | stop | final_chars | reentries | deadline | wall_s (untrusted) | deleg | brief_chars |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
)


def build_pi_direct_args(
    trace: Path,
    sentence: str,
    guards: bool = False,
    prompt: Path = PROMPT_FILE,
    prompt_mode: str = "append",
    thinking: str = "high",
) -> list[str]:
    """The worker alone. `append` keeps Pi's base prompt under the worker prompt (phases 0-2);
    `replace` sends the worker prompt only, which is what the shipped agent file does."""
    prompt_args = (
        ["--system-prompt", prompt.read_text()]
        if prompt_mode == "replace"
        else ["--append-system-prompt", str(prompt)]
    )
    args = [
        "pi",
        "-p",
        "--mode",
        "json",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--no-session",
        "--thinking",
        thinking,
        "--model",
        MODEL,
        "--tools",
        TOOLS,
        *prompt_args,
        "-e",
        str(RECORD_EXT),
    ]
    if guards:
        args += ["-e", str(GUARDS_EXT)]
    return [*args, sentence]


def child_env(
    parent: dict, trace: str, agent_dir: Path | None = None, offline: bool | None = None
) -> dict:
    """The worker's environment: the parent's, minus the repo venv that uv exports.

    Direct mode runs offline against the ladder's own agent directory.
    Delegated mode points Pi at the mirrored operator profile and keeps the
    network, which the hosted parent model needs.
    """
    env = {k: v for k, v in parent.items() if k != "VIRTUAL_ENV"}
    env["MELLUM_TRACE_FILE"] = str(trace)
    if agent_dir is not None:
        env["PI_CODING_AGENT_DIR"] = str(agent_dir)
    if offline is None:
        offline = agent_dir is None
    if offline:
        env["PI_OFFLINE"] = "1"
    else:
        env.pop("PI_OFFLINE", None)
    return env


def build_pi_delegated_args(sentence: str) -> list[str]:
    """The parent: its normal profile (model, Superpowers, pi-subagents), addressed to the worker."""
    return [
        "pi",
        "-p",
        "--mode",
        "json",
        "--no-session",
        "--thinking",
        "high",
        PARENT_PROMPT.format(sentence=sentence),
    ]


def build_pi_primary_args(sentence: str, plain: bool = False) -> list[str]:
    """Mellum as the primary agent, given the raw sentence.

    Two baselines the worker is measured against. Operator (default): no
    worker in the workspace, Superpowers and pi-subagents loaded as the
    operator has them — what "just swap the model" does. Plain: Pi's own base
    prompt and tools with no extensions, skills, or context files — the
    model's ceiling as a primary agent, separating Superpowers' effect from
    Pi's base prompt. Both load the recorder explicitly so the scorer sees the
    same events as direct mode.
    """
    plain_flags = (
        ["--no-extensions", "--no-skills", "--no-context-files"] if plain else []
    )
    return [
        "pi",
        "-p",
        "--mode",
        "json",
        "--no-session",
        *plain_flags,
        "--thinking",
        "high",
        "--model",
        MODEL,
        "-e",
        str(RECORD_EXT),
        sentence,
    ]


def parse_parent_json(stdout: str) -> dict:
    """What the parent did: whether it launched the worker, the brief it wrote, its final text."""
    brief, final, messages, calls = "", "", 0, 0
    for line in stdout.splitlines():
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        message = event.get("message") or {}
        if event.get("type") != "message_end" or message.get("role") != "assistant":
            continue
        messages += 1
        blocks = [b for b in (message.get("content") or []) if isinstance(b, dict)]
        final = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        for block in blocks:
            if block.get("type") == "toolCall" and block.get("name") == "subagent":
                arguments = block.get("arguments") or {}
                if arguments.get("agent") == "mellum-worker" and arguments.get("task"):
                    calls += 1
                    brief = brief or str(arguments["task"])
    return {
        "delegated": calls > 0,
        "brief": brief,
        "parent_final_chars": len(final.strip()),
        "parent_messages": messages,
        "subagent_calls": calls,
    }


def parse_pi_json(stdout: str, with_reentries: bool = False):
    """Final assistant stop reason and visible text from Pi's JSON event stream.

    With ``with_reentries`` also returns how many assistant messages carried
    more than one thinking block: the model re-opened ``<think>`` after a
    close, which gives it a fresh server-side thinking budget each time.
    """
    stop, text, reentries = None, "", 0
    for line in stdout.splitlines():
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        message = event.get("message") or {}
        if event.get("type") != "message_end" or message.get("role") != "assistant":
            continue
        stop = message.get("stopReason")
        blocks = [b for b in (message.get("content") or []) if isinstance(b, dict)]
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        if sum(b.get("type") == "thinking" for b in blocks) > 1:
            reentries += 1
    if with_reentries:
        return stop, text.strip(), reentries
    return stop, text.strip()


def git(ws: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ws, capture_output=True, text=True, check=False
    ).stdout


def prepare_workspace(rung: Rung, scratch: Path) -> Path:
    ws = copy_fixture(rung.fixture, scratch / f"rung{rung.number}")
    git(ws, "init", "-q")
    git(ws, "add", "-A")
    git(
        ws,
        "-c",
        "user.name=ladder",
        "-c",
        "user.email=ladder@localhost",
        "commit",
        "-qm",
        "baseline",
    )
    if (ws / "pyproject.toml").exists():
        subprocess.run(
            ["uv", "sync", "--offline"],
            cwd=ws,
            capture_output=True,
            timeout=300,
            check=False,
        )
    return ws


def baseline_index(ws: Path) -> tuple[set[str], dict[str, int]]:
    paths = {p for p in git(ws, "ls-files").split() if p}
    lines = {p: len((ws / p).read_text(errors="replace").splitlines()) for p in paths}
    return paths, lines


def read_events(trace: Path) -> list[dict]:
    if not trace.exists():
        return []
    return [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]


def run_once(
    rung: Rung,
    mode: str,
    prof: str,
    repeat: int,
    out: Path,
    deadline: int,
    versions: dict,
    guards: bool,
    plain: bool = False,
    prompt: Path = PROMPT_FILE,
    prompt_mode: str = "append",
    thinking: str = "high",
    subagents_config: dict | None = None,
) -> dict:
    scratch = Path(tempfile.mkdtemp(prefix="ladder-"))
    ws = prepare_workspace(rung, scratch)
    paths, lines = baseline_index(ws)
    trace = scratch / "trace.jsonl"
    if mode == "delegated":
        prepare_pi_workspace(ws, RECORD_EXT)
        agent_dir = mirror_agent_dir(
            Path.home() / ".pi" / "agent",
            scratch / "pi-agent",
            [ws],
            subagents_config=subagents_config,
        )
        env = child_env(dict(os.environ), str(trace), agent_dir)
        args = build_pi_delegated_args(rung.sentence)
    elif mode == "primary":
        agent_dir = mirror_agent_dir(
            Path.home() / ".pi" / "agent", scratch / "pi-agent", [ws]
        )
        env = child_env(dict(os.environ), str(trace), agent_dir, offline=False)
        args = build_pi_primary_args(rung.sentence, plain)
    else:
        agent_dir = direct_agent_dir(scratch / "pi-agent", prof)
        env = child_env(dict(os.environ), str(trace), agent_dir, offline=True)
        args = build_pi_direct_args(
            trace, rung.sentence, guards, prompt, prompt_mode, thinking
        )
    started = time.time()
    deadline_hit = False
    stdout = ""
    try:
        proc = subprocess.run(
            args,
            cwd=ws,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=deadline,
            check=False,
        )
        stdout = proc.stdout + ("\n[stderr]\n" + proc.stderr if proc.stderr else "")
    except subprocess.TimeoutExpired as error:
        deadline_hit = True
        captured = error.stdout or b""
        stdout = (
            captured.decode(errors="replace")
            if isinstance(captured, bytes)
            else str(captured)
        )
    wall = time.time() - started
    stop_reason, final_text, thinking_reentries = parse_pi_json(
        stdout, with_reentries=True
    )
    events = read_events(trace)
    git(ws, "add", "-A")
    record = {
        "rung": rung.number,
        "repeat": repeat,
        "profile": prof,
        "mode": mode,
        "harness": "pi",
        "plain": plain,
        "guards": guards,
        "subagents_config": subagents_config,
        "guards_env": json.loads(os.environ["MELLUM_GUARDS"])
        if os.environ.get("MELLUM_GUARDS")
        else None,
        "prompt_version": prompt_version(prompt) if mode == "direct" else None,
        "prompt_file": (
            str(prompt.relative_to(ROOT))
            if prompt.is_relative_to(ROOT)
            else str(prompt)
        )
        if mode == "direct"
        else None,
        "prompt_mode": prompt_mode if mode == "direct" else None,
        "thinking": thinking if mode == "direct" else None,
        "versions": versions,
        "sentence": rung.sentence,
        "started": started,
        "wall_seconds_untrusted": round(wall, 1),
        "deadline_hit": deadline_hit,
        "stop_reason": stop_reason,
        "final_text_chars": len(final_text),
        "thinking_reentries": thinking_reentries,
        "final_text_is": "parent" if mode == "delegated" else "worker",
        "parent": parse_parent_json(stdout) if mode == "delegated" else None,
        "baseline_lines": lines,
        "check": asdict(rung.check(ws, FIXTURES / rung.fixture)),
        "score": score(events, paths, lines).as_row(),
        "diff_stat": git(ws, "diff", "--cached", "--stat"),
        "files_created": [
            p
            for p in git(
                ws, "diff", "--cached", "--name-only", "--diff-filter=A"
            ).split()
            if p
        ],
        "workspace": str(ws),
    }
    variant = f"{'-guards' if guards else ''}{'-plain' if plain else ''}"
    run_dir = out / f"rung{rung.number}-{prof}-{mode}{variant}-r{repeat}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(record, indent=2, default=str))
    if trace.exists():
        shutil.copy(trace, run_dir / "trace.jsonl")
    (run_dir / "stdout.txt").write_text(stdout)
    (run_dir / "final.md").write_text(final_text)
    (run_dir / "diff.patch").write_text(git(ws, "diff", "--cached"))
    if record["parent"]:
        (run_dir / "brief.md").write_text(record["parent"]["brief"])
    return record


def table_row(record: dict) -> str:
    s, c = record["score"], record["check"]
    result = "pass" if c["passed"] else "FAIL"
    parent = record.get("parent") or {}
    deleg = parent.get("delegated", "") if parent else ""
    brief_chars = len(parent.get("brief", "")) if parent else ""
    return (
        f"| {record['rung']} | {record['profile']}{'+guards' if record['guards'] else ''} | {record['mode']} | "
        f"{record['repeat']} | {result} | {c['tests_unchanged']} | {s['requests']} | {s['tool_errors']} | "
        f"{s['edit_anchor_failures']} | {s['noop_edits']} | {s['write_existing']} | {s['write_shrink']} | {s['bash_file_mutations']} | "
        f"{s['max_identical_streak']} | {s['largest_prompt_chars']} | {s.get('nudges', 0)} | {record['stop_reason']} | {record['final_text_chars']} | {record.get('thinking_reentries', '')} | {record['deadline_hit']} | "
        f"{record['wall_seconds_untrusted']} | {deleg} | {brief_chars} |\n"
    )


def install_signal_handlers() -> None:
    """SIGTERM/SIGHUP exit through SystemExit so the profile restore in `finally` still runs."""

    def exit_on_signal(signum, _frame):
        raise SystemExit(128 + signum)

    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, exit_on_signal)


def tool_version(cmd: list[str]) -> str:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        ).stdout.strip()
    except OSError, subprocess.TimeoutExpired:
        return "unknown"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", choices=["pi"], default="pi")
    parser.add_argument(
        "--mode", choices=["direct", "delegated", "primary"], default="direct"
    )
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--rung", type=int, action="append", required=True)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--deadline", type=int, default=600)
    parser.add_argument("--guards", action="store_true")
    parser.add_argument(
        "--plain",
        action="store_true",
        help="primary mode: no extensions, skills, or context files (Pi's base prompt only)",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        default=PROMPT_FILE,
        help="direct mode: worker prompt file (default prompts/mellum-worker.md)",
    )
    parser.add_argument(
        "--prompt-mode",
        choices=["append", "replace"],
        default="append",
        help="direct mode: append to Pi's base prompt (phases 0-2) or replace it (the shipped agent file)",
    )
    parser.add_argument(
        "--thinking", default="high", help="direct mode: Pi thinking level"
    )
    parser.add_argument(
        "--subagents-config",
        type=json.loads,
        default=None,
        help="delegated mode: JSON that replaces pi-subagents' config.json in the mirrored agent dir",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--omlx", default="http://127.0.0.1:8001")
    args = parser.parse_args(argv)
    install_signal_handlers()

    client = AdminClient(args.omlx)
    versions = {
        "pi": tool_version(["pi", "--version"]),
        "omlx": tool_version(["omlx", "--version"]),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    table = args.out / "table.md"
    if not table.exists():
        table.write_text(HEADER)
    settings_path = Path.home() / ".omlx" / "model_settings.json"
    with profile(client, MODEL_ID, args.profile, settings_path) as live:
        versions["model_settings"] = {
            k: live.get(k)
            for k in (
                "max_tokens",
                "thinking_budget_tokens",
                "presence_penalty",
                "max_tool_result_tokens",
            )
        }
        for number in args.rung:
            for repeat in range(1, args.repeat + 1):
                record = run_once(
                    RUNGS[number],
                    args.mode,
                    args.profile,
                    repeat,
                    args.out,
                    args.deadline,
                    versions,
                    args.guards,
                    args.plain,
                    args.prompt,
                    args.prompt_mode,
                    args.thinking,
                    args.subagents_config,
                )
                row = table_row(record)
                with table.open("a") as stream:
                    stream.write(row)
                if args.mode == "direct" and record["score"]["effective_params"]:
                    check_effective_params(
                        record["score"]["effective_params"], args.profile
                    )
                print(row, end="", flush=True)


if __name__ == "__main__":
    main()
