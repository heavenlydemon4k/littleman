import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from littleman.db.models import Heartbeat


async def get_stale_running_heartbeats(
    db: AsyncSession, timeout_minutes: int
) -> list[Heartbeat]:
    """Return heartbeats that have been in RUNNING state longer than timeout_minutes.

    These represent sessions that crashed without marking themselves DONE or FAILED —
    e.g. the process was killed, hit OOM, or the machine rebooted. Without this check they
    would stay RUNNING forever and never be retried.

    Adopted from OpenClaw's stale-run detection pattern.
    """
    if timeout_minutes <= 0:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    result = await db.execute(
        select(Heartbeat)
        .where(Heartbeat.status == "RUNNING", Heartbeat.started_at <= cutoff)
        .order_by(Heartbeat.started_at)
    )
    return list(result.scalars().all())


# Exponential backoff delays for failed heartbeats (seconds): 30s → 2m → 10m → give up.
_RETRY_DELAYS = [30, 120, 600]


async def create_heartbeat(
    db: AsyncSession,
    fire_at: datetime,
    reason: str,
    session_type: str,
    context: dict[str, Any],
    spawned_by: str | None = None,
) -> Heartbeat:
    hb = Heartbeat(
        id=str(uuid.uuid4()),
        fire_at=fire_at,
        reason=reason,
        session_type=session_type,
        context=context,
        status="SCHEDULED",
        spawned_by=spawned_by,
    )
    db.add(hb)
    await db.commit()
    await db.refresh(hb)
    return hb


async def get_due_heartbeats(db: AsyncSession) -> list[Heartbeat]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Heartbeat)
        .where(Heartbeat.status == "SCHEDULED", Heartbeat.fire_at <= now)
        .order_by(Heartbeat.fire_at)
    )
    return list(result.scalars().all())


async def get_heartbeat(db: AsyncSession, heartbeat_id: str) -> Heartbeat | None:
    result = await db.execute(select(Heartbeat).where(Heartbeat.id == heartbeat_id))
    return result.scalar_one_or_none()


async def list_scheduled(db: AsyncSession) -> list[Heartbeat]:
    result = await db.execute(
        select(Heartbeat)
        .where(Heartbeat.status == "SCHEDULED")
        .order_by(Heartbeat.fire_at)
    )
    return list(result.scalars().all())


async def mark_running(db: AsyncSession, heartbeat_id: str) -> None:
    await db.execute(
        update(Heartbeat)
        .where(Heartbeat.id == heartbeat_id)
        .values(status="RUNNING", started_at=datetime.now(timezone.utc))
    )
    await db.commit()


async def mark_done(db: AsyncSession, heartbeat_id: str) -> None:
    await db.execute(
        update(Heartbeat)
        .where(Heartbeat.id == heartbeat_id)
        .values(status="DONE", completed_at=datetime.now(timezone.utc))
    )
    await db.commit()


async def mark_failed(db: AsyncSession, heartbeat_id: str, reason: str) -> None:
    await db.execute(
        update(Heartbeat)
        .where(Heartbeat.id == heartbeat_id)
        .values(
            status="FAILED",
            completed_at=datetime.now(timezone.utc),
            failure_reason=reason,
        )
    )
    await db.commit()


async def schedule_retry(
    db: AsyncSession,
    original: Heartbeat,
    failure_reason: str,
) -> "Heartbeat | None":
    """Schedule a retry of a failed heartbeat with exponential backoff.

    Retry count is tracked in the heartbeat's context under ``_retry_count``.
    Returns the new heartbeat, or None when max retries have been exhausted.
    """
    retry_count: int = (original.context or {}).get("_retry_count", 0)
    if retry_count >= len(_RETRY_DELAYS):
        return None

    delay = _RETRY_DELAYS[retry_count]
    fire_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
    retry_context = {**(original.context or {}), "_retry_count": retry_count + 1}

    return await create_heartbeat(
        db,
        fire_at=fire_at,
        reason=f"retry #{retry_count + 1}: {original.reason}",
        session_type=original.session_type,
        context=retry_context,
        spawned_by=original.id,
    )


async def cancel_heartbeat(db: AsyncSession, heartbeat_id: str) -> bool:
    result = await db.execute(select(Heartbeat).where(Heartbeat.id == heartbeat_id))
    hb = result.scalar_one_or_none()
    if not hb or hb.status != "SCHEDULED":
        return False
    await db.execute(
        update(Heartbeat).where(Heartbeat.id == heartbeat_id).values(status="CANCELLED")
    )
    await db.commit()
    return True


async def amend_heartbeat(
    db: AsyncSession,
    heartbeat_id: str,
    fire_at: datetime | None = None,
    reason: str | None = None,
    context: dict[str, Any] | None = None,
) -> Heartbeat | None:
    result = await db.execute(select(Heartbeat).where(Heartbeat.id == heartbeat_id))
    hb = result.scalar_one_or_none()
    if not hb or hb.status != "SCHEDULED":
        return None
    if fire_at is not None:
        hb.fire_at = fire_at
    if reason is not None:
        hb.reason = reason
    if context is not None:
        hb.context = {**(hb.context or {}), **context}
    await db.commit()
    await db.refresh(hb)
    return hb


def serialise(hb: Heartbeat) -> dict:
    return {
        "id": hb.id,
        "fire_at": hb.fire_at.isoformat() if hb.fire_at else None,
        "reason": hb.reason,
        "session_type": hb.session_type,
        "context": hb.context,
        "status": hb.status,
        "spawned_by": hb.spawned_by,
        "created_at": hb.created_at.isoformat() if hb.created_at else None,
    }
