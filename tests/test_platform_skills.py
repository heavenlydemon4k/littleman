import pytest

from littleman.skills.platform import make_platform_skills


def test_platform_skill_names():
    skills = {s["name"] for s in make_platform_skills(lambda: None)}
    assert "set_reminder" in skills
    assert "take_note" in skills
    assert "read_notes" in skills


@pytest.mark.asyncio
async def test_take_note_and_read_notes(db):
    from littleman.skills.registry import build_registry

    registry = build_registry(lambda: db)
    await registry.dispatch("take_note", {"topic": "ideas", "content": "build platform default"})
    result = await registry.dispatch("read_notes", {"topic": "ideas"})
    assert "build platform default" in str(result)
