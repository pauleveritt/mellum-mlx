from pathlib import Path

from ladder.run_ladder import PROMPT_FILE, build_pi_direct_args

ROOT = Path(__file__).resolve().parent.parent


def test_direct_args_are_the_clean_profile():
    args = build_pi_direct_args(Path("/tmp/trace.jsonl"), "fix it")
    for flag in (
        "-p",
        "--no-extensions",
        "--no-skills",
        "--no-context-files",
        "--no-session",
    ):
        assert flag in args
    assert args[args.index("--tools") + 1] == "read,grep,find,ls,bash,edit,write"
    assert args[args.index("--append-system-prompt") + 1] == str(PROMPT_FILE)
    assert args[-1] == "fix it"


def test_agent_file_body_matches_prompt():
    body = (ROOT / ".pi/agents/mellum-worker.md").read_text().split("---", 2)[2].strip()
    assert body == PROMPT_FILE.read_text().strip()


def test_parse_pi_json_extracts_final_stop_and_text():
    from ladder.run_ladder import parse_pi_json

    lines = [
        '{"type":"message_end","message":{"role":"user","content":"hi"}}',
        '{"type":"message_end","message":{"role":"assistant","stopReason":"toolUse","content":[{"type":"toolCall","name":"read"}]}}',
        '{"type":"message_end","message":{"role":"assistant","stopReason":"length","content":[{"type":"thinking","thinking":"..."}]}}',
        '{"type":"agent_end"}',
    ]
    stop, text = parse_pi_json("\n".join(lines))
    assert stop == "length" and text == ""
    stop, text = parse_pi_json(
        '{"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":[{"type":"text","text":"Done."}]}}'
    )
    assert stop == "stop" and text == "Done."


def test_direct_env_drops_virtual_env():
    from ladder.run_ladder import child_env

    env = child_env({"VIRTUAL_ENV": "/x", "PATH": "/bin"}, "/tmp/t.jsonl")
    assert "VIRTUAL_ENV" not in env and env["MELLUM_TRACE_FILE"] == "/tmp/t.jsonl"


def test_parse_pi_json_counts_thinking_reentries():
    from ladder.run_ladder import parse_pi_json

    two_blocks = (
        '{"type":"message_end","message":{"role":"assistant","stopReason":"toolUse","content":'
        '[{"type":"thinking","thinking":"a"},{"type":"text","text":"b"},{"type":"thinking","thinking":"c"}]}}'
    )
    one_block = (
        '{"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":'
        '[{"type":"thinking","thinking":"a"},{"type":"text","text":"Done."}]}}'
    )
    stop, text, reentries = parse_pi_json(
        f"{two_blocks}\n{one_block}", with_reentries=True
    )
    assert stop == "stop" and text == "Done." and reentries == 1


def test_run_once_never_inherits_stdin(monkeypatch, tmp_path):
    """Pi blocks forever on a non-TTY stdin that never reaches EOF; the worker must get DEVNULL."""
    import subprocess as sp

    from ladder import run_ladder
    from ladder.rungs import CheckResult, Rung

    seen = {}

    def fake_run(args, **kwargs):
        seen.update(kwargs)
        return sp.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(run_ladder.subprocess, "run", fake_run)
    monkeypatch.setattr(run_ladder, "prepare_workspace", lambda rung, scratch: scratch)
    monkeypatch.setattr(run_ladder, "baseline_index", lambda ws: (set(), {}))
    rung = Rung(
        1, "calculator", "fix it", ["true"], lambda ws, base: CheckResult(False, True)
    )
    run_ladder.run_once(rung, "direct", "baseline", 1, tmp_path / "out", 5, {}, False)
    assert seen.get("stdin") is sp.DEVNULL


def test_signal_handlers_raise_system_exit_so_finally_blocks_run():
    import signal

    from ladder.run_ladder import install_signal_handlers

    install_signal_handlers()
    for sig in (signal.SIGTERM, signal.SIGHUP):
        handler = signal.getsignal(sig)
        import pytest

        with pytest.raises(SystemExit):
            handler(sig, None)


def test_parse_parent_json_extracts_the_brief():
    from ladder.run_ladder import parse_parent_json

    lines = [
        '{"type":"message_end","message":{"role":"assistant","stopReason":"toolUse","content":[{"type":"toolCall","name":"subagent","arguments":{"agent":"mellum-worker","task":"Fix totalCents in calculator.js; run node --test"}}]}}',
        '{"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":[{"type":"text","text":"Done: 3/3 tests pass."}]}}',
    ]
    parent = parse_parent_json("\n".join(lines))
    assert parent["delegated"] is True
    assert parent["brief"] == "Fix totalCents in calculator.js; run node --test"
    assert parent["parent_final_chars"] == len("Done: 3/3 tests pass.")
    assert parent["subagent_calls"] == 1


def test_parse_parent_json_reports_no_delegation():
    from ladder.run_ladder import parse_parent_json

    line = (
        '{"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":'
        '[{"type":"toolCall","name":"edit","arguments":{}},{"type":"text","text":"I fixed it myself."}]}}'
    )
    parent = parse_parent_json(line)
    assert (
        parent["delegated"] is False
        and parent["brief"] == ""
        and parent["subagent_calls"] == 0
    )


def test_delegated_args_address_the_worker_by_name():
    from ladder.run_ladder import build_pi_delegated_args

    args = build_pi_delegated_args("fix it")
    assert (
        args[:2] == ["pi", "-p"]
        and "--no-session" in args
        and "--no-extensions" not in args
    )
    assert args[-1] == "Use mellum-worker to do this: fix it"


def test_direct_env_is_offline_and_uses_the_profile_agent_dir():
    from ladder.run_ladder import child_env

    env = child_env(
        {"PATH": "/bin"},
        "/tmp/t.jsonl",
        agent_dir=__import__("pathlib").Path("/tmp/agent"),
        offline=True,
    )
    assert env["PI_OFFLINE"] == "1" and env["PI_CODING_AGENT_DIR"] == "/tmp/agent"


def test_primary_args_run_mellum_as_the_parent_with_the_recorder():
    from ladder.run_ladder import MODEL, RECORD_EXT, build_pi_primary_args

    args = build_pi_primary_args("fix it")
    assert args[:2] == ["pi", "-p"] and "--no-session" in args and "--no-extensions" not in args
    assert args[args.index("--model") + 1] == MODEL
    assert args[args.index("-e") + 1] == str(RECORD_EXT)
    assert args[-1] == "fix it"
