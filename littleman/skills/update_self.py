"""update_self skill — conversational refinement of SOUL.md.

Custom onboarding produces a minimal SOUL.md stub. This skill lets the agent (and operator,
via the agent) iteratively refine that stub into a durable identity. It is intentionally gated
to the custom onboarding path so guided-onboarding identities (already compiled from a full
questionnaire) are not casually overwritten.
"""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from littleman.config import settings
from littleman.db.models import Profile


def make_update_self_skill(
    db_session_factory: Callable[[], AsyncSession],
) -> list[dict[str, Any]]:
    async def update_self(content: str, mode: str = "replace") -> dict[str, Any]:
        async with db_session_factory() as db:
            result = await db.execute(select(Profile).where(Profile.id == 1))
            profile = result.scalar_one_or_none()

            if profile is None or profile.onboarding_path != "custom":
                return {
                    "updated": False,
                    "reason": "update_self is only available for the custom onboarding path",
                }

        soul_path = settings.workspace_dir / "SOUL.md"
        if not soul_path.exists():
            return {"updated": False, "reason": "SOUL.md does not exist; run onboarding first"}

        mode = (mode or "replace").lower()
        if mode not in ("replace", "append", "prepend"):
            return {"updated": False, "reason": f"unknown mode: {mode}"}

        if mode == "replace":
            new_content = content
        else:
            existing = soul_path.read_text(encoding="utf-8")
            if mode == "append":
                new_content = existing + "\n\n" + content
            else:  # prepend
                new_content = content + "\n\n" + existing

        soul_path.write_text(new_content, encoding="utf-8")
        return {
            "updated": True,
            "mode": mode,
            "bytes": len(new_content.encode("utf-8")),
        }

    return [
        {
            "name": "update_self",
            "fn": update_self,
            "description": (
                "Refine the agent's SOUL.md identity document through conversation. "
                "Only available when onboarding used the custom path. "
                "Modes: replace (full rewrite), append (add to end), prepend (add to start)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Markdown content to write into SOUL.md.",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["replace", "append", "prepend"],
                        "description": "How to combine the new content with existing SOUL.md.",
                    },
                },
                "required": ["content"],
            },
            "cost": "LOW",
        }
    ]
