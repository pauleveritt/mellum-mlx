import subprocess

from ladder.sandbox import make_sandbox


def test_sandbox_is_a_git_committed_copy_outside_the_repo(tmp_path):
    ws = make_sandbox(1, tmp_path)
    assert ws.is_relative_to(tmp_path)
    assert (ws / "calculator.js").exists() and not (ws / ".venv").exists()
    log = subprocess.run(["git", "log", "--oneline"], cwd=ws, capture_output=True, text=True).stdout
    assert "baseline" in log


def test_sandbox_carries_the_worker_definition(tmp_path):
    ws = make_sandbox(1, tmp_path)
    assert (ws / ".pi" / "agents" / "mellum-worker.md").read_text().startswith("---\nname: mellum-worker")
