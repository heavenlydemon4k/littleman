"""The Main session — the agent's autonomous activity stream.

OpenClaw has a 'main' session that is the agent's own context. Littleman mirrors that: every
autonomous (heartbeat-driven) or manual agent run narrates itself into a pinned chat session
with the fixed id 'main'. The user can open it like any chat to watch what the agent did and
why, while ordinary user↔LLM chats live in their own sessions.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from littleman.db.models import ChatMessage, ChatSession

MAIN_SESSION_ID = "main"
MAIN_TITLE = "Main — agent (autonomous)"


async def ensure_main(db: AsyncSession) -> None:
    result = await db.execute(select(ChatSession).where(ChatSession.id == MAIN_SESSION_ID))
    if result.scalar_one_or_none() is None:
        db.add(ChatSession(id=MAIN_SESSION_ID, title=MAIN_TITLE))
        await db.commit()


async def log_main(db: AsyncSession, content: str, role: str = "assistant") -> None:
    """Append a narration message to the Main session."""
    await ensure_main(db)
    db.add(
        ChatMessage(
            id=str(uuid.uuid4()),
            session_id=MAIN_SESSION_ID,
            role=role,
            content=content,
        )
    )
    await db.commit()
