"""Generic platform skills available to the default littleman.platform application."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def make_platform_skills(
    db_session_factory: Callable[[], Any] | None = None,
) -> list[dict[str, Any]]:
    """Return skill definitions for the platform default application."""
    from littleman.heartbeat import store
    from littleman.skills.kb import make_kb_skills

    kb_factory = db_session_factory or (lambda: None)
    kb_skills = {s["name"]: s["fn"] for s in make_kb_skills(kb_factory)}
    write_to_kb = kb_skills["write_to_kb"]
    read_from_kb = kb_skills["read_from_kb"]
    search_kb = kb_skills["search_kb"]

    async def set_reminder(title: str, fire_at: str, reason: str | None = None) -> dict[str, Any]:
        """Schedule a future heartbeat reminder."""
        fire_dt = _parse_iso_datetime(fire_at)
        factory = db_session_factory or (lambda: None)
        async with factory() as db:
            hb = await store.create_heartbeat(
                db,
                fire_at=fire_dt,
                reason=reason or title,
                session_type="FULL_CYCLE",
                context={"reminder_title": title},
                spawned_by=None,
            )
            return {"heartbeat_id": hb.id, "fire_at": hb.fire_at.isoformat()}

    async def take_note(
        topic: str,
        content: str,
        source_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        """Persist a general note to the knowledge base."""
        return await write_to_kb(
            topic=topic,
            content=content,
            source_urls=source_urls or [],
            confidence="HIGH",
        )

    async def read_notes(topic: str | None = None, query: str | None = None) -> dict[str, Any]:
        """Read notes by topic or full-text query."""
        if topic:
            return await read_from_kb(topic)
        if query:
            return await search_kb(query)
        return {"entries": []}

    return [
        {
            "name": "set_reminder",
            "fn": set_reminder,
            "description": "Schedule a future reminder. fire_at is an ISO 8601 datetime.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "fire_at": {"type": "string", "format": "date-time"},
                    "reason": {"type": "string"},
                },
                "required": ["title", "fire_at"],
            },
            "cost": "LOW",
            "chat_safe": True,
        },
        {
            "name": "take_note",
            "fn": take_note,
            "description": "Save a note to the knowledge base under a topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "content": {"type": "string"},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["topic", "content"],
            },
            "cost": "LOW",
            "chat_safe": True,
        },
        {
            "name": "read_notes",
            "fn": read_notes,
            "description": "Read notes by topic or search query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": [],
            },
            "cost": "LOW",
            "chat_safe": True,
        },
    ]
