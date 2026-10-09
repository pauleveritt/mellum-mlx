import subprocess

import pytest

from ladder.rungs import FIXTURES, RUNGS, copy_fixture


def run_tests(rung, cwd):
    return subprocess.run(
        rung.test_cmd, cwd=cwd, capture_output=True, text=True, check=False
    ).returncode


def copy(rung, tmp_path):
    return copy_fixture(rung.fixture, tmp_path / "ws")


@pytest.mark.parametrize("n", [1, 4, 5])
def test_baseline_fails_before_fix(n, tmp_path):
    rung = RUNGS[n]
    assert run_tests(rung, copy(rung, tmp_path)) != 0


@pytest.mark.parametrize("n", [2, 3])
def test_baseline_passes_before_change(n, tmp_path):
    rung = RUNGS[n]
    assert run_tests(rung, copy(rung, tmp_path)) == 0


def test_rung2_check_accepts_added_test(tmp_path):
    rung = RUNGS[2]
    ws = copy(rung, tmp_path)
    (ws / "ledger.py").write_text(
        (ws / "ledger.py").read_text()
        + "\n\ndef balance(entries):\n    return sum(e.amount for e in entries)\n"
    )
    (ws / "test_ledger.py").write_text(
        (ws / "test_ledger.py").read_text()
        + "\n\ndef test_balance():\n    from ledger import Entry, balance\n"
        "    assert balance([Entry('a', 5), Entry('b', -2)]) == 3\n"
    )
    result = rung.check(ws, FIXTURES / rung.fixture)
    assert result.passed and result.tests_unchanged


def test_rung5_decoy_edit_fails(tmp_path):
    rung = RUNGS[5]
    ws = copy(rung, tmp_path)
    (ws / "exports_legacy.py").write_text("# touched\n")
    assert not rung.check(ws, FIXTURES / rung.fixture).passed


def test_check_treats_a_deleted_file_as_changed_not_a_crash(tmp_path):
    rung = RUNGS[5]
    ws = copy(rung, tmp_path)
    (ws / "exports_legacy.py").unlink()
    result = rung.check(ws, FIXTURES / rung.fixture)
    assert result.passed is False


def test_check_treats_a_hung_test_run_as_a_failure(monkeypatch, tmp_path):
    import subprocess as sp

    from ladder import rungs

    def hang(cmd, **kwargs):
        raise sp.TimeoutExpired(cmd, kwargs.get("timeout", 0))

    monkeypatch.setattr(rungs.subprocess, "run", hang)
    rung = RUNGS[1]
    ws = copy(rung, tmp_path)
    assert rung.check(ws, FIXTURES / rung.fixture).passed is False
