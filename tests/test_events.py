"""Live action feed tests — emit/tail/prune + the dispatch and session emit points."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from littleman.agent import events
from littleman.db.models import Base
from littleman.skills.registry import SkillRegistry


@pytest_asyncio.fixture
async def events_db(monkeypatch):
    """In-memory DB wired into events.emit via the app's AsyncSessionLocal name.

    emit/prune import AsyncSessionLocal at call time, so patching the module attribute
    routes their writes here. StaticPool keeps one connection so rows persist across the
    fresh sessions emit opens per call.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("littleman.db.connection.AsyncSessionLocal", factory)
    events.set_session(None)
    yield factory
    events.set_session(None)
    await engine.dispose()


@pytest.mark.asyncio
async def test_emit_noop_without_session(events_db):
    await events.emit(events.STAGE, {"x": 1})  # no session bound
    async with events_db() as db:
        assert await events.recent(db) == []


@pytest.mark.asyncio
async def test_emit_writes_with_session(events_db):
    events.set_session("sess-1")
    await events.emit(events.STAGE, {"label": "hi"})
    async with events_db() as db:
        ev = await events.recent(db)
    assert len(ev) == 1
    assert ev[0]["type"] == "stage"
    assert ev[0]["agent_session_id"] == "sess-1"
    assert ev[0]["payload"]["label"] == "hi"


@pytest.mark.asyncio
async def test_tail_returns_only_events_after_seq(events_db):
    events.set_session("s")
    await events.emit(events.STAGE, {"n": 1})
    await events.emit(events.STAGE, {"n": 2})
    async with events_db() as db:
        all_ev = await events.recent(db)
        rest = await events.tail(db, since_seq=all_ev[0]["seq"])
    assert [e["payload"]["n"] for e in rest] == [2]


@pytest.mark.asyncio
async def test_dispatch_emits_tool_call_and_result(events_db):
    events.set_session("s")
    reg = SkillRegistry()

    async def ok(**_):
        return {"result": "fine"}

    reg.register("noop", ok, "desc", {"type": "object"})
    await reg.dispatch("noop", {"a": 1})

    async with events_db() as db:
        ev = await events.recent(db)
    assert [e["type"] for e in ev] == ["tool_call", "tool_result"]
    assert ev[0]["payload"]["name"] == "noop"
    assert ev[1]["payload"]["ok"] is True


@pytest.mark.asyncio
async def test_dispatch_emits_failure_then_reraises(events_db):
    events.set_session("s")
    reg = SkillRegistry()

    async def boom(**_):
        raise RuntimeError("nope")

    reg.register("boom", boom, "desc", {"type": "object"})
    with pytest.raises(RuntimeError):
        await reg.dispatch("boom", {})

    async with events_db() as db:
        ev = await events.recent(db)
    assert ev[-1]["type"] == "tool_result"
    assert ev[-1]["payload"]["ok"] is False
    assert "nope" in ev[-1]["payload"]["error"]


@pytest.mark.asyncio
async def test_dispatch_no_events_without_session(events_db):
    events.set_session(None)
    reg = SkillRegistry()

    async def ok(**_):
        return {"ok": True}

    reg.register("noop", ok, "desc", {"type": "object"})
    await reg.dispatch("noop", {})
    async with events_db() as db:
        assert await events.recent(db) == []


@pytest.mark.asyncio
async def test_prune_keeps_recent_sessions(events_db):
    for sid in ["a", "b", "c"]:
        events.set_session(sid)
        await events.emit(events.STAGE, {})
    deleted = await events.prune(keep_sessions=2)
    assert deleted == 1
    async with events_db() as db:
        ev = await events.recent(db)
    assert {e["agent_session_id"] for e in ev} == {"b", "c"}


@pytest.mark.asyncio
async def test_prune_noop_under_threshold(events_db):
    events.set_session("only")
    await events.emit(events.STAGE, {})
    assert await events.prune(keep_sessions=50) == 0


@pytest.mark.asyncio
async def test_full_session_run_emits_feed(tmp_path, monkeypatch):
    """A real run_session (fake mode) emits the wake's start, stages and done, and clears
    the feed binding afterwards. Exercises the contextvar + session.py emit points end-to-end."""
    from littleman.config import settings
    from littleman.llm.provider import ScriptedProvider, set_provider
    from littleman.meta import construct

    ws = tmp_path / "workspace"
    (ws / "construct").mkdir(parents=True)
    for name in construct.ALL_DOCS:
        stem = name.replace(".md", "")
        (ws / "construct" / f"{stem}.template.md").write_text(
            f"<!-- TEMPLATE {name} -->\n", encoding="utf-8"
        )
    (ws / "SOUL.md").write_text("You are Littleman. Mission: test the feed.", encoding="utf-8")
    (ws / "SKILLS.md").write_text("Skills available.", encoding="utf-8")
    monkeypatch.setattr(settings, "workspace_dir", ws)
    monkeypatch.setattr(settings, "llm_mode", "fake")
    set_provider(ScriptedProvider())
    construct.seed_from_templates()

    # One shared in-memory DB for run_session's own writes AND the event feed. session.py
    # binds AsyncSessionLocal at import, so patch both that name and the connection module's.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("littleman.db.connection.AsyncSessionLocal", factory)
    monkeypatch.setattr("littleman.agent.session.AsyncSessionLocal", factory)

    from littleman.agent.session import run_session

    events.set_session(None)
    try:
        await run_session()
    finally:
        set_provider(None)

    async with factory() as db:
        ev = await events.recent(db, limit=500)
    types = [e["type"] for e in ev]
    assert types[0] == "session_start"
    assert "stage" in types
    assert types[-1] == "session_done"
    # The feed binding must not leak into the next serial wake.
    assert events.current_session() is None
    await engine.dispose()
