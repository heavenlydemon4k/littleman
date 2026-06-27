"""Tests for per-turn workspace markdown discovery."""

from __future__ import annotations

import pytest

from littleman.config import settings
from littleman.meta.construct import discover_workspace_files, workspace_prompt_block


@pytest.mark.asyncio
async def test_discover_workspace_files_excludes_construct(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_dir", tmp_path / "workspace")
    ws = settings.workspace_dir
    (ws / "plans").mkdir(parents=True)
    (ws / "plans" / "mvp.md").write_text("# MVP", encoding="utf-8")
    (ws / "construct").mkdir(parents=True)
    (ws / "construct" / "PRIORITIES.md").write_text("priorities", encoding="utf-8")

    files = discover_workspace_files()
    paths = [p for p, _ in files]
    assert "plans/mvp.md" in paths
    assert "construct/PRIORITIES.md" not in paths


@pytest.mark.asyncio
async def test_workspace_prompt_block_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_dir", tmp_path / "workspace")
    ws = settings.workspace_dir
    (ws / "notes").mkdir(parents=True)
    (ws / "notes" / "long.md").write_text("x" * 2000, encoding="utf-8")

    block = workspace_prompt_block(max_chars=500)
    assert "workspace/notes/long.md" in block
    assert "…[truncated]…" in block or len(block) <= 500
