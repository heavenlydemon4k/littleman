import pytest

from littleman.skills.platform import make_platform_skills


def test_platform_skill_names():
    skills = {s["name"] for s in make_platform_skills(lambda: None)}
    assert "set_reminder" in skills
    assert "take_note" in skills
    assert "read_notes" in skills


@pytest.mark.asyncio
async def test_set_reminder_creates_heartbeat(db):
    from datetime import datetime

    from littleman.heartbeat import store
    from littleman.skills.registry import build_registry

    registry = build_registry(lambda: db)
    result = await registry.dispatch(
        "set_reminder",
        {
            "title": "review finding",
            "fire_at": "2026-01-01T00:00:00Z",
            "reason": "exercise ISO datetime parsing",
        },
    )
    assert "heartbeat_id" in result
    hb = await store.get_heartbeat(db, result["heartbeat_id"])
    assert hb is not None
    assert hb.reason == "exercise ISO datetime parsing"
    assert hb.context == {"reminder_title": "review finding"}
    assert hb.status == "SCHEDULED"
    assert hb.fire_at == datetime(2026, 1, 1, 0, 0, 0)


@pytest.mark.asyncio
async def test_take_note_and_read_notes(db):
    from littleman.skills.registry import build_registry

    registry = build_registry(lambda: db)
    await registry.dispatch("take_note", {"topic": "ideas", "content": "build platform default"})
    result = await registry.dispatch("read_notes", {"topic": "ideas"})
    assert "build platform default" in str(result)
