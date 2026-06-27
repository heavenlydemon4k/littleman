"""Tests for the OpenClaw SKILL.md filesystem loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from littleman.config import settings
from littleman.skills.openclaw_loader import _parse_frontmatter, load_openclaw_skills


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_dir", tmp_path / "workspace")
    return settings.workspace_dir


def test_openclaw_loader_ignores_doc_only_manifests(tmp_path, monkeypatch):
    from littleman.config import Settings

    oc_dir = tmp_path / "openclaw" / "skills"
    oc_dir.mkdir(parents=True)
    (oc_dir / "my_skill.md").write_text(
        "---\nname: my_skill\n---\n# My skill\nJust docs, no implementation.",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "littleman.skills.openclaw_loader.settings",
        Settings(workspace_dir=tmp_path),
    )
    skills = load_openclaw_skills()
    assert not skills


def test_parse_frontmatter_extracts_metadata_and_body():
    text = """---
name: echo
description: repeats the input
cost: LOW
---
# Echo

Repeats whatever you send.
"""
    meta, body = _parse_frontmatter(text)
    assert meta["name"] == "echo"
    assert meta["description"] == "repeats the input"
    assert "# Echo" in body


def test_parse_frontmatter_without_frontmatter():
    text = "# Hello\n\nNo frontmatter here."
    meta, body = _parse_frontmatter(text)
    assert meta == {}
    assert body == text


@pytest.mark.asyncio
async def test_load_openclaw_skill_without_impl(temp_workspace):
    skills_dir = temp_workspace / "openclaw" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "future_skill.md").write_text(
        "---\nname: future_skill\ndescription: A skill from the future.\nregister: true\n---\n",
        encoding="utf-8",
    )

    skills = load_openclaw_skills()
    assert len(skills) == 1
    assert skills[0]["name"] == "future_skill"

    result = await skills[0]["fn"]()
    assert "no Python implementation" in result["error"]


@pytest.mark.asyncio
async def test_load_openclaw_skill_with_impl(temp_workspace, monkeypatch):
    async def fake_impl(message: str) -> dict:
        return {"echo": message}

    skills_dir = temp_workspace / "openclaw" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "echo.md").write_text(
        "---\nname: echo\ndescription: Echoes input.\nparameters:\n  type: object\n  properties:\n    message:\n      type: string\n  required: [message]\n---\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "littleman.skills.openclaw_loader._load_impl", lambda name: fake_impl if name == "echo" else None
    )

    skills = load_openclaw_skills()
    assert any(s["name"] == "echo" for s in skills)

    echo = next(s for s in skills if s["name"] == "echo")
    result = await echo["fn"](message="hi")
    assert result == {"echo": "hi"}
