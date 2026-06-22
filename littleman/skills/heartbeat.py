"""Heartbeat skills — the agent's interface to its own schedule.

These wrap littleman.heartbeat.store so the agent can create, amend, cancel, and list its own
future activations as tool calls.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from littleman.heartbeat import store


def _parse_dt(value: str) -> datetime:
    # Accept a trailing Z as UTC.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def make_heartbeat_skills(db_factory: Callable[[], AsyncSession]) -> list[dict]:
    async def create_heartbeat(
        fire_at: str,
        reason: str,
        session_type: str,
        context: dict[str, Any] | None = None,
        spawned_by: str | None = None,
    ) -> dict:
        async with db_factory() as db:
            hb = await store.create_heartbeat(
                db,
                fire_at=_parse_dt(fire_at),
                reason=reason,
                session_type=session_type,
                context=context or {},
                spawned_by=spawned_by,
            )
            return store.serialise(hb)

    async def amend_heartbeat(
        heartbeat_id: str,
        fire_at: str | None = None,
        reason: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict:
        async with db_factory() as db:
            hb = await store.amend_heartbeat(
                db,
                heartbeat_id,
                fire_at=_parse_dt(fire_at) if fire_at else None,
                reason=reason,
                context=context,
            )
            if hb is None:
                return {"amended": False, "reason": "not found or not in SCHEDULED state"}
            return {"amended": True, **store.serialise(hb)}

    async def cancel_heartbeat(heartbeat_id: str, reason: str) -> dict:
        async with db_factory() as db:
            ok = await store.cancel_heartbeat(db, heartbeat_id)
            return {"cancelled": ok, "heartbeat_id": heartbeat_id, "reason": reason}

    async def list_scheduled_heartbeats() -> dict:
        async with db_factory() as db:
            rows = await store.list_scheduled(db)
            return {"heartbeats": [store.serialise(h) for h in rows], "count": len(rows)}

    return [
        {
            "name": "create_heartbeat",
            "fn": create_heartbeat,
            "description": "Schedule a future agent session at a specific time with intent-carrying context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fire_at": {"type": "string", "description": "ISO 8601 datetime"},
                    "reason": {"type": "string"},
                    "session_type": {
                        "type": "string",
                        "enum": ["RESOLVE", "RESEARCH", "MONITOR", "FULL_CYCLE"],
                    },
                    "context": {"type": "object"},
                    "spawned_by": {"type": "string"},
                },
                "required": ["fire_at", "reason", "session_type"],
            },
            "cost": "LOW",
        },
        {
            "name": "amend_heartbeat",
            "fn": amend_heartbeat,
            "description": "Modify a scheduled heartbeat's time, reason, or context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "heartbeat_id": {"type": "string"},
                    "fire_at": {"type": "string"},
                    "reason": {"type": "string"},
                    "context": {"type": "object"},
                },
                "required": ["heartbeat_id"],
            },
            "cost": "LOW",
        },
        {
            "name": "cancel_heartbeat",
            "fn": cancel_heartbeat,
            "description": "Cancel a scheduled heartbeat whose trigger is no longer relevant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "heartbeat_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["heartbeat_id", "reason"],
            },
            "cost": "LOW",
        },
        {
            "name": "list_scheduled_heartbeats",
            "fn": list_scheduled_heartbeats,
            "description": "List all currently scheduled heartbeats, soonest first.",
            "parameters": {"type": "object", "properties": {}, "required": []},
            "cost": "LOW",
        },
    ]
