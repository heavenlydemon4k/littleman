import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from littleman.db.models import KBEntry


def make_kb_skills(db_factory: Callable[[], AsyncSession]) -> list[dict]:
    async def write_to_kb(
        topic: str,
        content: str,
        source_urls: list[str] | None = None,
        confidence: str = "MEDIUM",
        expires_hours: float | None = None,
    ) -> dict:
        async with db_factory() as db:
            expires_at = None
            if expires_hours:
                expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

            entry = KBEntry(
                id=str(uuid.uuid4()),
                topic=topic,
                content=content,
                source_urls=source_urls or [],
                confidence=confidence,
                expires_at=expires_at,
                linked_market_ids=[],
            )
            db.add(entry)
            await db.commit()
            return {"id": entry.id, "topic": topic, "written": True}

    async def read_from_kb(topic: str) -> dict:
        async with db_factory() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(KBEntry)
                .where(
                    KBEntry.topic == topic,
                    or_(KBEntry.expires_at == None, KBEntry.expires_at > now),
                )
                .order_by(KBEntry.gathered_at.desc())
            )
            entries = result.scalars().all()
            return {
                "topic": topic,
                "entries": [
                    {
                        "id": e.id,
                        "content": e.content,
                        "confidence": e.confidence,
                        "source_urls": e.source_urls,
                        "gathered_at": e.gathered_at.isoformat() if e.gathered_at else None,
                        "expires_at": e.expires_at.isoformat() if e.expires_at else None,
                    }
                    for e in entries
                ],
                "count": len(entries),
            }

    async def search_kb(query: str, limit: int = 10) -> dict:
        async with db_factory() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(KBEntry)
                .where(or_(KBEntry.expires_at == None, KBEntry.expires_at > now))
                .order_by(KBEntry.gathered_at.desc())
                .limit(100)
            )
            entries = result.scalars().all()

            query_lower = query.lower()
            matches = [
                e for e in entries
                if query_lower in e.topic.lower() or query_lower in e.content.lower()
            ][:limit]

            return {
                "query": query,
                "results": [
                    {
                        "id": e.id,
                        "topic": e.topic,
                        "content": e.content[:500] + ("..." if len(e.content) > 500 else ""),
                        "confidence": e.confidence,
                        "gathered_at": e.gathered_at.isoformat() if e.gathered_at else None,
                    }
                    for e in matches
                ],
                "count": len(matches),
            }

    return [
        {
            "name": "write_to_kb",
            "fn": write_to_kb,
            "description": "Write research findings to the knowledge base for future sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "content": {"type": "string"},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                    "expires_hours": {"type": "number"},
                },
                "required": ["topic", "content"],
            },
            "cost": "LOW",
        },
        {
            "name": "read_from_kb",
            "fn": read_from_kb,
            "description": "Retrieve stored knowledge on a topic. Check before doing new research.",
            "parameters": {
                "type": "object",
                "properties": {"topic": {"type": "string"}},
                "required": ["topic"],
            },
            "cost": "LOW",
        },
        {
            "name": "search_kb",
            "fn": search_kb,
            "description": "Full-text search across knowledge base entries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
            "cost": "LOW",
        },
    ]
