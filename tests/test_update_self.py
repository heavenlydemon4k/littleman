"""Tests for the update_self skill."""

from __future__ import annotations

import pytest

from littleman.config import settings
from littleman.db.models import Profile
from littleman.skills.update_self import make_update_self_skill


@pytest.fixture
def skill(db):
    skills = make_update_self_skill(lambda: db)
    return {s["name"]: s["fn"] for s in skills}["update_self"]


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_dir", tmp_path / "workspace")
    return settings.workspace_dir


@pytest.mark.asyncio
async def test_update_self_replace_custom_path(skill, temp_workspace, db):
    from littleman.api.routes.onboarding import _compile_soul_template

    p = Profile(id=1, display_name="A", purpose="Be a research assistant.", onboarding_path="custom")
    db.add(p)
    await db.commit()

    soul = _compile_soul_template("A", "Be a research assistant.", "custom", {})
    temp_workspace.mkdir(parents=True, exist_ok=True)
    (temp_workspace / "SOUL.md").write_text(soul, encoding="utf-8")

    res = await skill(content="## New section\n\nDetails.", mode="replace")
    assert res["updated"] is True

    content = (temp_workspace / "SOUL.md").read_text(encoding="utf-8")
    assert "## New section" in content
    assert "Be a research assistant" not in content


@pytest.mark.asyncio
async def test_update_self_gated_to_custom_path(skill, temp_workspace, db):
    p = Profile(id=1, display_name="A", purpose="Trade.", onboarding_path="guided")
    db.add(p)
    await db.commit()

    temp_workspace.mkdir(parents=True, exist_ok=True)
    (temp_workspace / "SOUL.md").write_text("# SOUL", encoding="utf-8")

    res = await skill(content="## New", mode="replace")
    assert res["updated"] is False
    assert "custom onboarding path" in res["reason"]


@pytest.mark.asyncio
async def test_update_self_append(skill, temp_workspace, db):
    p = Profile(id=1, display_name="A", purpose="X", onboarding_path="custom")
    db.add(p)
    await db.commit()

    temp_workspace.mkdir(parents=True, exist_ok=True)
    (temp_workspace / "SOUL.md").write_text("# SOUL", encoding="utf-8")

    res = await skill(content="## Extra", mode="append")
    assert res["updated"] is True

    content = (temp_workspace / "SOUL.md").read_text(encoding="utf-8")
    assert content.startswith("# SOUL")
    assert "## Extra" in content
