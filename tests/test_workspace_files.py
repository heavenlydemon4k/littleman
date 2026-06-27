"""Tests for generic workspace file skills."""

from __future__ import annotations

import pytest

from littleman.config import settings
from littleman.skills.workspace_files import (
    WorkspacePathError,
    make_workspace_file_skills,
)


@pytest.fixture
def skills(temp_workspace):
    by_name = {s["name"]: s["fn"] for s in make_workspace_file_skills()}
    return by_name


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_dir", tmp_path / "workspace")
    return settings.workspace_dir


@pytest.mark.asyncio
async def test_write_and_read_workspace_file(skills, temp_workspace):
    res = await skills["write_workspace_file"](path="plans/mvp.md", content="# MVP\n\nPlan here.")
    assert res["written"] is True

    read = await skills["read_workspace_file"](path="plans/mvp.md")
    assert read["exists"] is True
    assert read["content"] == "# MVP\n\nPlan here."


@pytest.mark.asyncio
async def test_read_missing_file(skills, temp_workspace):
    read = await skills["read_workspace_file"](path="missing.md")
    assert read["exists"] is False


@pytest.mark.asyncio
async def test_list_workspace_files(skills, temp_workspace):
    await skills["write_workspace_file"](path="notes/a.md", content="a")
    await skills["write_workspace_file"](path="notes/b.md", content="b")

    listing = await skills["list_workspace_files"](directory="notes")
    names = {e["name"] for e in listing["entries"]}
    assert names == {"a.md", "b.md"}


@pytest.mark.asyncio
async def test_update_workspace_file_append(skills, temp_workspace):
    await skills["write_workspace_file"](path="log.md", content="line 1\n")
    res = await skills["update_workspace_file"](path="log.md", content="line 2\n", mode="append")
    assert res["updated"] is True

    read = await skills["read_workspace_file"](path="log.md")
    assert read["content"] == "line 1\nline 2\n"


@pytest.mark.asyncio
async def test_update_workspace_file_replace(skills, temp_workspace):
    await skills["write_workspace_file"](path="scratch.md", content="old")
    res = await skills["update_workspace_file"](path="scratch.md", content="new", mode="replace")
    assert res["updated"] is True

    read = await skills["read_workspace_file"](path="scratch.md")
    assert read["content"] == "new"


@pytest.mark.asyncio
async def test_path_traversal_rejected(skills, temp_workspace):
    with pytest.raises(WorkspacePathError):
        await skills["read_workspace_file"](path="../outside.md")


@pytest.mark.asyncio
async def test_non_text_file_rejected(skills, temp_workspace):
    with pytest.raises(WorkspacePathError):
        await skills["write_workspace_file"](path="malware.exe", content="bad")
