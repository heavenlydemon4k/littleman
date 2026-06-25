"""Agent activity events — the live action feed substrate.

A wake runs in a different process than the API/WebSocket server (`python -m littleman
scheduler` vs `uvicorn`), and SQLite has no pub/sub, so the event stream is delivered
through the database: any process appends rows here; the API tails the table over a
WebSocket (WAL mode lets a reader see writes committed by another process/connection).

Emission is always **best-effort** — a failure to record an event must never break a wake.
The active wake's session id lives in a ContextVar set once at the top of a session run, so
callers (skill dispatch, the ReAct loop) don't have to thread it through every call.
"""

from __future__ import annotations

import contextvars
import json
import logging
import uuid
from typing import Any

from sqlalchemy import delete, func, select

log = logging.getLogger("events")

_current_session: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agent_session_id", default=None
)

KEEP_SESSIONS = 50
_PAYLOAD_LIMIT = 1500

# Event types, for reference / validation.
SESSION_START = "session_start"
STAGE = "stage"
REASONING = "reasoning"
TOOL_CALL = "tool_call"
TOOL_RESULT = "tool_result"
SESSION_DONE = "session_done"


def set_session(session_id: str | None) -> None:
    """Mark the wake currently executing in this process (or clear it with None)."""
    _current_session.set(session_id)


def current_session() -> str | None:
    return _current_session.get()


def shrink(value: Any, limit: int = _PAYLOAD_LIMIT) -> str:
    """Render a value to a bounded string so payloads stay small."""
    s = value if isinstance(value, str) else json.dumps(value, default=str)
    return s if len(s) <= limit else s[: limit - 1] + "…"


async def emit(
    event_type: str, payload: dict[str, Any] | None = None, *, session_id: str | None = None
) -> None:
    """Append one activity event. Best-effort: never raises, no-ops without a session."""
    sid = session_id or _current_session.get()
    if not sid:
        return
    try:
        from littleman.db.connection import AsyncSessionLocal
        from littleman.db.models import AgentEvent

        async with AsyncSessionLocal() as db:
            db.add(
                AgentEvent(
                    id=str(uuid.uuid4()),
                    agent_session_id=sid,
                    type=event_type,
                    payload=payload or {},
                )
            )
            await db.commit()
    except Exception:  # noqa: BLE001 — telemetry must never break a wake
        log.debug("event emit failed", exc_info=True)


def _serialise(e: Any) -> dict:
    return {
        "seq": e.seq,
        "id": e.id,
        "agent_session_id": e.agent_session_id,
        "type": e.type,
        "payload": e.payload,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


async def tail(db: Any, since_seq: int, limit: int = 200) -> list[dict]:
    """Events with seq greater than `since_seq`, oldest-first (the live cursor)."""
    from littleman.db.models import AgentEvent

    rows = (
        await db.execute(
            select(AgentEvent)
            .where(AgentEvent.seq > since_seq)
            .order_by(AgentEvent.seq)
            .limit(limit)
        )
    ).scalars().all()
    return [_serialise(r) for r in rows]


async def recent(db: Any, limit: int = 100) -> list[dict]:
    """The most recent events, returned oldest-first for initial paint / replay."""
    from littleman.db.models import AgentEvent

    rows = (
        await db.execute(
            select(AgentEvent).order_by(AgentEvent.seq.desc()).limit(limit)
        )
    ).scalars().all()
    return [_serialise(r) for r in reversed(rows)]


async def prune(keep_sessions: int = KEEP_SESSIONS) -> int:
    """Keep events for the most recent `keep_sessions` agent sessions; delete older ones.

    Bounds table growth over long autonomous runs while preserving replayable recent
    history. Best-effort: returns the number of rows deleted (0 on any failure).
    """
    try:
        from littleman.db.connection import AsyncSessionLocal
        from littleman.db.models import AgentEvent

        async with AsyncSessionLocal() as db:
            rows = (
                await db.execute(
                    select(AgentEvent.agent_session_id)
                    .group_by(AgentEvent.agent_session_id)
                    .order_by(func.max(AgentEvent.seq).desc())
                )
            ).all()
            if len(rows) <= keep_sessions:
                return 0
            keep = {r[0] for r in rows[:keep_sessions]}
            result = await db.execute(
                delete(AgentEvent).where(AgentEvent.agent_session_id.notin_(keep))
            )
            await db.commit()
            return result.rowcount or 0
    except Exception:  # noqa: BLE001 — pruning must never break a wake
        log.debug("event prune failed", exc_info=True)
        return 0
