from __future__ import annotations

import pytest

from littleman.config import settings
from littleman.llm import runtime
from littleman.skills.system_config import make_system_config_skills


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_dir", tmp_path / "workspace")
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    return settings.workspace_dir


@pytest.fixture
def skills(temp_workspace):
    return {s["name"]: s["fn"] for s in make_system_config_skills()}


@pytest.mark.asyncio
async def test_inspect_system_config_redacts_api_key(skills, temp_workspace):
    runtime.set_override({"api_key": "secret", "primary_model": "openai/test-model"})
    (temp_workspace / "SOUL.md").write_text("# SOUL\n\nTest.", encoding="utf-8")

    res = await skills["inspect_system_config"](include_soul=True)

    assert res["runtime"]["api_key_set"] is True
    assert "api_key" not in res["runtime"]
    assert res["runtime"]["primary_model"] == "openai/test-model"
    assert res["soul"]["content"].startswith("# SOUL")


@pytest.mark.asyncio
async def test_propose_soul_update_does_not_write(skills, temp_workspace):
    soul = temp_workspace / "SOUL.md"
    soul.write_text("# SOUL\n\nOriginal.", encoding="utf-8")

    res = await skills["propose_soul_update"](
        content="## Extra\n\nNew detail.",
        mode="append",
        rationale="test",
    )

    assert res["ok"] is True
    assert res["requires_confirmation"] is True
    assert "New detail" in res["proposed_content"]
    assert soul.read_text(encoding="utf-8") == "# SOUL\n\nOriginal."


@pytest.mark.asyncio
async def test_apply_soul_update_requires_confirmation(skills, temp_workspace):
    soul = temp_workspace / "SOUL.md"
    soul.write_text("# SOUL", encoding="utf-8")

    res = await skills["apply_soul_update"](content="# New", confirm=False)

    assert res["updated"] is False
    assert soul.read_text(encoding="utf-8") == "# SOUL"


@pytest.mark.asyncio
async def test_apply_soul_update_writes_when_confirmed(skills, temp_workspace):
    soul = temp_workspace / "SOUL.md"
    soul.write_text("# SOUL", encoding="utf-8")

    res = await skills["apply_soul_update"](
        content="## Extra",
        mode="append",
        confirm=True,
    )

    assert res["updated"] is True
    assert "## Extra" in soul.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_set_runtime_config_requires_confirmation(skills):
    before = runtime.active()["primary_model"]

    res = await skills["set_runtime_config"](
        values={"primary_model": "openai/new-model"},
        confirm=False,
    )

    assert res["updated"] is False
    assert runtime.active()["primary_model"] == before


@pytest.mark.asyncio
async def test_set_runtime_config_filters_unknown_keys(skills):
    res = await skills["set_runtime_config"](
        values={"primary_model": "openai/new-model", "unknown": "ignored"},
        confirm=True,
    )

    assert res["updated"] is True
    assert res["changed"] == ["primary_model"]
    assert res["ignored"] == ["unknown"]
    assert runtime.active()["primary_model"] == "openai/new-model"
