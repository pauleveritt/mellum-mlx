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
