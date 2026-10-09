import json
from pathlib import Path

from ladder.pi_profile import mirror_agent_dir, prepare_pi_workspace

ROOT = Path(__file__).resolve().parent.parent


def fake_agent_dir(root: Path) -> Path:
    src = root / "agent"
    (src / "git" / "pkg").mkdir(parents=True)
    (src / "npm").mkdir()
    (src / "sessions").mkdir()
    (src / "sessions" / "private.jsonl").write_text("secret")
    (src / "extensions").mkdir()
    for name in ("settings.json", "models.json", "auth.json"):
        (src / name).write_text("{}")
    (src / "AGENTS.md").write_text("notes")
    return src


def test_mirror_skips_sessions_and_writes_nothing_to_source(tmp_path):
    src = fake_agent_dir(tmp_path)
    before = sorted(p.relative_to(src) for p in src.rglob("*"))
    dest = mirror_agent_dir(src, tmp_path / "mirror", [tmp_path / "ws"])
    assert not (dest / "sessions").exists()
    assert (dest / "git").is_symlink() and (dest / "npm").is_symlink()
    assert (dest / "settings.json").read_text() == "{}" and (dest / "AGENTS.md").read_text() == "notes"
    assert json.loads((dest / "trust.json").read_text()) == {str(tmp_path / "ws"): True}
    assert sorted(p.relative_to(src) for p in src.rglob("*")) == before


def test_ladder_agent_file_appends_recorder_to_guards(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    prepare_pi_workspace(ws, Path("/abs/record-pi.js"), skill=False)
    text = (ws / ".pi" / "agents" / "mellum-worker.md").read_text()
    assert "subagentOnlyExtensions: ./.pi/extensions/mellum-guards.ts, /abs/record-pi.js\n" in text
    assert (ws / ".pi" / "extensions" / "mellum-guards.ts").exists()
    committed = (ROOT / ".pi" / "agents" / "mellum-worker.md").read_text()
    assert "record-pi" not in committed


def test_prepare_pi_workspace_skill_toggle(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    prepare_pi_workspace(a, Path("/abs/record-pi.js"), skill=False)
    prepare_pi_workspace(b, Path("/abs/record-pi.js"), skill=True)
    assert not (a / ".pi" / "skills").exists()
    assert (b / ".pi" / "skills" / "delegate-to-mellum" / "SKILL.md").exists()
