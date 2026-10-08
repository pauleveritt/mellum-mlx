import json

from ladder.rescore import rescore_dir


def test_rescore_recomputes_score_from_trace_and_baseline(tmp_path):
    run = tmp_path / "rung1-x-r1"; run.mkdir()
    (run / "trace.jsonl").write_text(json.dumps(
        {"type": "tool_call", "toolName": "write", "input": {"path": "a.py", "content": "x\n"}}) + "\n")
    (run / "run.json").write_text(json.dumps({"score": {"stale": True}, "baseline_lines": {"a.py": 30}}))
    changed = rescore_dir(tmp_path)
    assert changed == 1
    assert json.loads((run / "run.json").read_text())["score"]["write_shrink"] == 1


def test_rescore_backfills_thinking_reentries_from_stdout(tmp_path):
    run = tmp_path / "rung1-x-r1"; run.mkdir()
    (run / "trace.jsonl").write_text("")
    (run / "stdout.txt").write_text('{"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":'
                                    '[{"type":"thinking","thinking":"a"},{"type":"text","text":"x"},{"type":"thinking","thinking":"b"}]}}\n')
    (run / "run.json").write_text(json.dumps({"score": {}, "baseline_lines": {}, "check": {"passed": True, "tests_unchanged": True},
                                              "stop_reason": "stop", "final_text_chars": 1, "rung": 1, "repeat": 1, "profile": "p", "mode": "direct", "guards": False, "deadline_hit": False, "wall_seconds_untrusted": 1}))
    rescore_dir(tmp_path)
    assert json.loads((run / "run.json").read_text())["thinking_reentries"] == 1
