"""Tests for DB-backed mental construct storage."""

from __future__ import annotations

import pytest

from littleman.db.models import ConstructDoc
from littleman.meta import construct
from littleman.meta import construct_store as store


@pytest.fixture
def enable_db_construct(monkeypatch):
    """Enable the DB-backed construct flag for a single test."""
    monkeypatch.setattr(construct.settings, "db_backed_construct", True)


@pytest.mark.asyncio
async def test_construct_store_crud(db):
    assert await store.read_doc(db, "PRIORITIES.md") == ""

    row = await store.write_doc(db, "PRIORITIES.md", "priority one")
    assert row.name == "PRIORITIES.md"
    assert row.content == "priority one"

    assert await store.read_doc(db, "PRIORITIES.md") == "priority one"

    await store.write_doc(db, "PRIORITIES.md", "priority two")
    assert await store.read_doc(db, "PRIORITIES.md") == "priority two"


@pytest.mark.asyncio
async def test_construct_store_read_many(db):
    await store.write_doc(db, "SELF.md", "self content")
    await store.write_doc(db, "CALENDAR.md", "calendar content")

    result = await store.read_many(db, ("SELF.md", "CALENDAR.md", "MISSING.md"))
    assert result["SELF.md"] == "self content"
    assert result["CALENDAR.md"] == "calendar content"
    assert result["MISSING.md"] == ""


@pytest.mark.asyncio
async def test_construct_store_append(db):
    await store.write_doc(db, "REFLECTION.md", "first entry")
    await store.append_to_doc(db, "REFLECTION.md", "second entry")

    content = await store.read_doc(db, "REFLECTION.md")
    assert "first entry" in content
    assert "second entry" in content


@pytest.mark.asyncio
async def test_sync_from_files(db, tmp_path, monkeypatch):
    monkeypatch.setattr(construct.settings, "workspace_dir", tmp_path)
    construct_dir = tmp_path / "construct"
    construct_dir.mkdir()
    (construct_dir / "PRIORITIES.md").write_text("file priorities", encoding="utf-8")

    docs = {"PRIORITIES.md": "file priorities", "SELF.md": ""}
    summary = await store.sync_from_files(db, docs)
    assert summary["created"] == 2

    await store.write_doc(db, "PRIORITIES.md", "db priorities")
    summary = await store.sync_from_files(db, docs)
    assert summary["updated"] == 1
    assert summary["unchanged"] == 1


@pytest.mark.asyncio
async def test_db_backed_write_renders_mirror(db, tmp_path, monkeypatch, enable_db_construct):
    monkeypatch.setattr(construct.settings, "workspace_dir", tmp_path)
    construct_dir = tmp_path / "construct"
    construct_dir.mkdir()

    from littleman.db.connection import AsyncSessionLocal

    # Seed the DB row directly.
    async with AsyncSessionLocal() as session:
        session.add(ConstructDoc(name="PRIORITIES.md", content="from db"))
        await session.commit()

    construct.write_doc("PRIORITIES.md", "new content")

    mirror = (construct_dir / "PRIORITIES.md").read_text(encoding="utf-8")
    assert mirror == "new content"

    async with AsyncSessionLocal() as session:
        row = await session.get(ConstructDoc, "PRIORITIES.md")
        assert row.content == "new content"


@pytest.mark.asyncio
async def test_db_backed_load_reads_db(db, tmp_path, monkeypatch, enable_db_construct):
    monkeypatch.setattr(construct.settings, "workspace_dir", tmp_path)
    construct_dir = tmp_path / "construct"
    construct_dir.mkdir()

    # Mirror file has stale content.
    (construct_dir / "PRIORITIES.md").write_text("stale file", encoding="utf-8")

    from littleman.db.connection import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        session.add(ConstructDoc(name="PRIORITIES.md", content="fresh db"))
        await session.commit()

    c = construct.load()
    assert c.priorities == "fresh db"


@pytest.mark.asyncio
async def test_db_backed_append_reflection(db, tmp_path, monkeypatch, enable_db_construct):
    monkeypatch.setattr(construct.settings, "workspace_dir", tmp_path)
    construct_dir = tmp_path / "construct"
    construct_dir.mkdir()

    from littleman.db.connection import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        session.add(ConstructDoc(name="REFLECTION.md", content="existing"))
        await session.commit()

    construct.append_reflection("new reflection")

    async with AsyncSessionLocal() as session:
        row = await session.get(ConstructDoc, "REFLECTION.md")
        assert "existing" in row.content
        assert "new reflection" in row.content

    mirror = (construct_dir / "REFLECTION.md").read_text(encoding="utf-8")
    assert "new reflection" in mirror
