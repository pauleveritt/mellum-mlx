import json
from pathlib import Path

from ladder.score import bash_mutates, call_key, score

EV = Path(__file__).parent / "fixtures_score"


def load(name):
    return [json.loads(line) for line in (EV / name).read_text().splitlines() if line]


def test_pass_run_counts_tools():
    s = score(load("pass.jsonl"), {"calculator.js"}, {"calculator.js": 3})
    assert s.tool_calls_by_name == {"read": 1, "edit": 1, "bash": 1}
    assert s.tool_errors == 0
    assert s.write_existing == []
    assert s.max_identical_streak == 1
    assert s.requests == 1


def test_write_existing_only_counts_baseline_paths():
    s = score(load("clobber.jsonl"), {"export.py"}, {"export.py": 40})
    assert s.write_existing == [{"path": "export.py", "lines_before": 40, "lines_after": 2}]
    assert score(load("clobber.jsonl"), set(), {}).write_existing == []


def test_identical_streak_counts_successful_repeats():
    assert score(load("loop.jsonl"), set(), {}).max_identical_streak == 6


def test_anchor_failures_and_noop_edits():
    s = score(load("loop.jsonl"), set(), {})
    assert s.edit_anchor_failures == 2
    assert s.noop_edits == 1


def test_bash_mutations_heredoc_and_redirect():
    assert bash_mutates("cat > a.py <<'EOF'\nx\nEOF")
    assert bash_mutates("cd src && echo hi >> log.txt")
    assert bash_mutates("printf 'x' | tee out.py")
    assert not bash_mutates("uv run pytest -q 2>&1")
    assert not bash_mutates("grep -rn fetch_rows . ")
    assert score(load("heredoc.jsonl"), set(), {}).bash_file_mutations == 1


def test_call_key_is_order_insensitive():
    assert call_key("edit", {"a": 1, "b": 2}) == call_key("edit", {"b": 2, "a": 1})


def test_pi_anchor_wording_counts_as_anchor_failure():
    events = [
        {"type": "tool_call", "toolName": "edit", "input": {"path": "a.py", "edits": []}},
        {"type": "tool_result", "toolName": "edit", "isError": True,
         "content": [{"type": "text", "text": "Could not find the exact text in a.py. The old text must match exactly."}]},
        {"type": "tool_call", "toolName": "edit", "input": {"path": "a.py", "edits": [1]}},
        {"type": "tool_result", "toolName": "edit", "isError": True,
         "content": [{"type": "text", "text": "Could not find edits[1] in a.py."}]},
    ]
    assert score(events, set(), {}).edit_anchor_failures == 2


def test_write_shrink_flags_only_shrinking_writes():
    grow = {"type": "tool_call", "toolName": "write", "input": {"path": "a.py", "content": "1\n2\n3\n4\n"}}
    shrink = {"type": "tool_call", "toolName": "write", "input": {"path": "b.py", "content": "1\n"}}
    s = score([grow, shrink], {"a.py", "b.py"}, {"a.py": 2, "b.py": 40})
    assert len(s.write_existing) == 2 and s.write_shrink == 1


def test_nudges_count_guard_messages_in_requests():
    req = {"type": "provider_request", "payload": {"messages": [
        {"role": "user", "content": "[mellum-guard] Your last turn ended with no reply."},
        {"role": "user", "content": "[mellum-guard] Your last turn ended with no reply."},
        {"role": "user", "content": "fix it"}]}}
    assert score([req], set(), {}).nudges == 2
