"""Database-backed storage for the mental construct.

ConstructDoc rows are the source of truth. The workspace/construct/*.md files remain as
human-readable mirrors that are re-rendered whenever a doc changes. This keeps the agent's
cognition auditable via files while making reads/writes coherent across processes.

Functions here are async because they touch the database. Synchronous callers in the existing
construct.py module use an internal async-to-sync bridge or continue to read files as a fallback.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from littleman.db.models import ConstructDoc


async def read_doc(db: AsyncSession, name: str) -> str:
    """Return the current content of a construct doc, or '' if absent."""
    row = await db.get(ConstructDoc, name)
    return row.content if row is not None else ""


async def write_doc(db: AsyncSession, name: str, content: str) -> ConstructDoc:
    """Write (or upsert) a construct doc."""
    row = await db.get(ConstructDoc, name)
    if row is None:
        row = ConstructDoc(name=name, content=content)
        db.add(row)
    else:
        row.content = content
    await db.commit()
    return row


async def read_many(db: AsyncSession, names: tuple[str, ...]) -> dict[str, str]:
    """Read several docs at once; missing names come back as ''."""
    result = await db.execute(select(ConstructDoc).where(ConstructDoc.name.in_(names)))
    by_name = {row.name: row.content for row in result.scalars().all()}
    return {name: by_name.get(name, "") for name in names}


async def append_to_doc(db: AsyncSession, name: str, entry: str, separator: str = "\n\n") -> ConstructDoc:
    """Append an entry to a doc (used for REFLECTION.md)."""
    existing = await read_doc(db, name)
    suffix = "" if not existing or existing.endswith(separator) else separator
    return await write_doc(db, name, existing + suffix + entry.strip() + "\n")


async def sync_from_files(db: AsyncSession, docs: dict[str, str]) -> dict[str, Any]:
    """Bulk-import file contents into ConstructDoc rows.

    Only writes rows that are missing or whose on-disk content differs, so it is safe to call
    at startup. Returns a summary of created/updated/unchanged counts.
    """
    created = updated = unchanged = 0
    for name, content in docs.items():
        row = await db.get(ConstructDoc, name)
        if row is None:
            db.add(ConstructDoc(name=name, content=content))
            created += 1
        elif row.content != content:
            row.content = content
            updated += 1
        else:
            unchanged += 1
    await db.commit()
    return {"created": created, "updated": updated, "unchanged": unchanged}
