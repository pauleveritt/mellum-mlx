import json

from ladder.summarize import comparison_table, summarize


def rec(rung, passed, profile="baseline", **score):
    s = {
        "requests": 5,
        "tool_errors": 0,
        "edit_anchor_failures": 0,
        "noop_edits": 0,
        "write_existing": 0,
        "bash_file_mutations": 0,
        "max_identical_streak": 1,
        "largest_prompt_chars": 1000,
    }
    s.update(score)
    return {
        "rung": rung,
        "profile": profile,
        "deadline_hit": False,
        "check": {"passed": passed, "tests_unchanged": True},
        "score": s,
    }


def write_runs(dir_, records):
    for i, r in enumerate(records):
        d = dir_ / f"run{i}"
        d.mkdir()
        (d / "run.json").write_text(json.dumps(r))


def test_summarize_counts_passes_and_flags_nonzero_columns(tmp_path):
    write_runs(
        tmp_path,
        [
            rec(1, True),
            rec(1, True),
            rec(1, False, write_existing=1),
            rec(2, True, max_identical_streak=6),
        ],
    )
    s = summarize(tmp_path)
    assert s["rungs"][1]["passed"] == 2 and s["rungs"][1]["runs"] == 3
    assert s["rungs"][2]["passed"] == 1
    assert s["nonzero"] == {"write_existing": 1, "max_identical_streak>=5": 1}


def test_comparison_table_has_a_row_per_rung(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    write_runs(a, [rec(1, False), rec(2, True)])
    write_runs(b, [rec(1, True, profile="tuned"), rec(2, True, profile="tuned")])
    table = comparison_table({"baseline": summarize(a), "tuned": summarize(b)})
    assert "| 1 | 0/1 | 1/1 |" in table and "| 2 | 1/1 | 1/1 |" in table


def test_summarize_flags_empty_final_and_non_stop(tmp_path):
    r = rec(1, False)
    r["stop_reason"] = "length"
    r["final_text_chars"] = 0
    write_runs(tmp_path, [r, rec(1, True)])
    assert summarize(tmp_path)["nonzero"] == {"empty_final": 1, "stop_reason!=stop": 1}


def test_summarize_flags_window_repeats_the_loop_breaker_would_see(tmp_path):
    write_runs(tmp_path, [rec(1, True, max_identical_in_window=5), rec(1, True)])
    assert summarize(tmp_path)["nonzero"] == {"max_identical_in_window>=5": 1}
