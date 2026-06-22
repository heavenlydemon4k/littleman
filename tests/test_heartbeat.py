"""Heartbeat store tests — create, amend, cancel, lifecycle, cascade lineage."""

from datetime import datetime, timedelta, timezone

import pytest

from littleman.heartbeat import store


def _future(minutes=60):
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def _past(minutes=5):
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


@pytest.mark.asyncio
async def test_create_and_get(db):
    hb = await store.create_heartbeat(
        db, fire_at=_future(), reason="check market A", session_type="RESOLVE",
        context={"positions_to_check": ["pos_1"]},
    )
    fetched = await store.get_heartbeat(db, hb.id)
    assert fetched is not None
    assert fetched.reason == "check market A"
    assert fetched.context["positions_to_check"] == ["pos_1"]
    assert fetched.status == "SCHEDULED"


@pytest.mark.asyncio
async def test_due_heartbeats_only_returns_past_scheduled(db):
    await store.create_heartbeat(db, fire_at=_past(), reason="due now", session_type="MONITOR", context={})
    await store.create_heartbeat(db, fire_at=_future(), reason="later", session_type="MONITOR", context={})
    due = await store.get_due_heartbeats(db)
    assert len(due) == 1
    assert due[0].reason == "due now"


@pytest.mark.asyncio
async def test_lifecycle_running_done(db):
    hb = await store.create_heartbeat(db, fire_at=_past(), reason="x", session_type="MONITOR", context={})
    await store.mark_running(db, hb.id)
    assert (await store.get_heartbeat(db, hb.id)).status == "RUNNING"
    await store.mark_done(db, hb.id)
    done = await store.get_heartbeat(db, hb.id)
    assert done.status == "DONE"
    assert done.completed_at is not None


@pytest.mark.asyncio
async def test_mark_failed_records_reason(db):
    hb = await store.create_heartbeat(db, fire_at=_past(), reason="x", session_type="MONITOR", context={})
    await store.mark_running(db, hb.id)
    await store.mark_failed(db, hb.id, "boom")
    failed = await store.get_heartbeat(db, hb.id)
    assert failed.status == "FAILED"
    assert failed.failure_reason == "boom"


@pytest.mark.asyncio
async def test_cancel_only_scheduled(db):
    hb = await store.create_heartbeat(db, fire_at=_future(), reason="x", session_type="MONITOR", context={})
    assert await store.cancel_heartbeat(db, hb.id) is True
    assert (await store.get_heartbeat(db, hb.id)).status == "CANCELLED"
    # Cancelling again fails — no longer SCHEDULED.
    assert await store.cancel_heartbeat(db, hb.id) is False


@pytest.mark.asyncio
async def test_amend_merges_context(db):
    hb = await store.create_heartbeat(
        db, fire_at=_future(), reason="orig", session_type="RESEARCH", context={"a": 1},
    )
    amended = await store.amend_heartbeat(db, hb.id, reason="updated", context={"b": 2})
    assert amended.reason == "updated"
    assert amended.context == {"a": 1, "b": 2}


@pytest.mark.asyncio
async def test_cascade_lineage_via_spawned_by(db):
    parent = await store.create_heartbeat(db, fire_at=_past(), reason="parent", session_type="FULL_CYCLE", context={})
    child = await store.create_heartbeat(
        db, fire_at=_future(), reason="child", session_type="RESOLVE", context={}, spawned_by=parent.id,
    )
    assert child.spawned_by == parent.id
