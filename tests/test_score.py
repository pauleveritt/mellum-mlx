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
    assert s.write_existing == [
        {"path": "export.py", "lines_before": 40, "lines_after": 2}
    ]
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
        {
            "type": "tool_call",
            "toolName": "edit",
            "input": {"path": "a.py", "edits": []},
        },
        {
            "type": "tool_result",
            "toolName": "edit",
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": "Could not find the exact text in a.py. The old text must match exactly.",
                }
            ],
        },
        {
            "type": "tool_call",
            "toolName": "edit",
            "input": {"path": "a.py", "edits": [1]},
        },
        {
            "type": "tool_result",
            "toolName": "edit",
            "isError": True,
            "content": [{"type": "text", "text": "Could not find edits[1] in a.py."}],
        },
    ]
    assert score(events, set(), {}).edit_anchor_failures == 2


def test_write_shrink_flags_only_shrinking_writes():
    grow = {
        "type": "tool_call",
        "toolName": "write",
        "input": {"path": "a.py", "content": "1\n2\n3\n4\n"},
    }
    shrink = {
        "type": "tool_call",
        "toolName": "write",
        "input": {"path": "b.py", "content": "1\n"},
    }
    s = score([grow, shrink], {"a.py", "b.py"}, {"a.py": 2, "b.py": 40})
    assert len(s.write_existing) == 2 and s.write_shrink == 1


def test_nudges_count_guard_messages_in_requests():
    req = {
        "type": "provider_request",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "[mellum-guard] Your last turn ended with no reply.",
                },
                {
                    "role": "user",
                    "content": "[mellum-guard] Your last turn ended with no reply.",
                },
                {"role": "user", "content": "fix it"},
            ]
        },
    }
    assert score([req], set(), {}).nudges == 2


def test_bash_mutates_ignores_quoted_operators_and_null_sinks():
    for command in (
        'python -c "print(1 > 0)"',
        "grep -v '>' f",
        'node -e "[1].map(x => x)"',
        'echo "a->b"',
        "python - <<EOF\nprint(1)\nEOF",
        'cat <<<"abc"',
        "pytest >> /dev/null && echo ok",
        "pytest | tee /dev/null",
    ):
        assert not bash_mutates(command), command


def test_bash_mutates_catches_in_place_editors_and_moves():
    for command in (
        "sed -i s/a/b/ f.py",
        "perl -i -pe s/a/b/ f.py",
        "mv a.py b.py",
        "cp a.py b.py",
        "cd sub && cat > f.py <<EOF\nx\nEOF",
    ):
        assert bash_mutates(command), command


def test_max_identical_in_window_counts_non_adjacent_repeats_like_the_loop_breaker():
    calls = []
    for i in range(6):
        calls.append(
            {"type": "tool_call", "toolName": "read", "input": {"path": "app.py"}}
        )
        calls.append(
            {"type": "tool_call", "toolName": "read", "input": {"path": f"other{i}.py"}}
        )
    s = score(calls, set(), {})
    assert s.max_identical_streak == 1
    assert s.max_identical_in_window == 6


def test_effective_params_come_from_the_first_request():
    events = [
        {
            "type": "provider_request",
            "payload": {
                "temperature": 1,
                "top_p": 0.95,
                "top_k": 20,
                "min_p": 0,
                "seed": 42,
                "max_tokens": 16384,
                "presence_penalty": 0,
                "messages": [],
            },
        },
        {"type": "provider_request", "payload": {"temperature": 0, "messages": []}},
    ]
    s = score(events, set(), {})
    assert s.effective_params == {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 20,
        "min_p": 0,
        "seed": 42,
        "max_tokens": 16384,
        "presence_penalty": 0,
    }


def test_loop_breaker_would_block_replays_the_real_guard():
    # Six identical calls: the ported breaker admits five and blocks the sixth.
    calls = [
        {"type": "tool_call", "toolName": "read", "input": {"path": "a"}}
        for _ in range(6)
    ]
    assert score(calls[:5], set(), {}).loop_breaker_would_block == 0
    assert score(calls, set(), {}).loop_breaker_would_block == 1
