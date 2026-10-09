from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / ".pi" / "skills" / "delegate-to-mellum" / "SKILL.md"


def test_skill_has_frontmatter_and_the_brief_template():
    text = SKILL.read_text()
    head, body = text.split("---", 2)[1], text.split("---", 2)[2]
    assert "name: delegate-to-mellum" in head and "description:" in head
    for field in ("Files:", "Change:", "Test command:", "Done when:"):
        assert field in body, field
    assert "empty" in body and "re-dispatch" in body
