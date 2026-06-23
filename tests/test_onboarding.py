"""Onboarding contract tests (Slice 0): status → welcome → complete."""

import pytest

from littleman.config import settings
from littleman.llm import runtime


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_dir", tmp_path / "workspace")
    monkeypatch.setattr(settings, "llm_mode", "fake")  # SOUL compile uses the template path
    return tmp_path


@pytest.mark.asyncio
async def test_status_not_onboarded_initially(db, temp_workspace):
    from littleman.api.routes.onboarding import status

    result = await status(db)
    assert result["onboarded"] is False
    assert result["display_name"] is None


@pytest.mark.asyncio
async def test_welcome_then_complete_marks_onboarded(db, temp_workspace, monkeypatch):
    from littleman.api.routes.onboarding import (
        CompleteBody,
        WelcomeBody,
        complete,
        status,
        welcome,
    )

    # welcome persists name + purpose and points the runtime at the model
    await welcome(
        WelcomeBody(
            display_name="Jude",
            purpose="Trade Polymarket markets for profit autonomously.",
            provider="openai",
            model="openai/moonshot-v1-128k",
        ),
        db,
    )
    assert runtime.active()["primary_model"] == "openai/moonshot-v1-128k"

    s1 = await status(db)
    assert s1["onboarded"] is False  # welcome alone does not complete onboarding
    assert s1["display_name"] == "Jude"

    # welcome() points the runtime at a real model; force the deterministic template path so
    # this unit test does not hit the network (the rich LLM compile is verified live).
    runtime.set_override({"mode": "fake"})

    # complete compiles SOUL.md and marks onboarded
    res = await complete(CompleteBody(path="guided", answers={"objective": "Find edges"}), db)
    assert res["ok"] is True
    assert res["first_light_session_id"] == "main"

    s2 = await status(db)
    assert s2["onboarded"] is True
    assert s2["path"] == "guided"

    soul = (temp_workspace / "workspace" / "SOUL.md").read_text()
    assert "Trade Polymarket markets" in soul
    assert "Jude" in soul
    assert "Find edges" in soul

    # The full guided answers are persisted on the profile for later rich interpretation.
    from littleman.api.routes.onboarding import _get_profile
    prof = await _get_profile(db)
    assert prof.answers == {"objective": "Find edges"}

    runtime.set_override({"mode": "real"})  # reset


@pytest.mark.asyncio
async def test_complete_requires_welcome_first(db, temp_workspace):
    from littleman.api.routes.onboarding import CompleteBody, complete

    res = await complete(CompleteBody(path="custom"), db)
    assert res["ok"] is False


@pytest.mark.asyncio
async def test_custom_path_soul_stub(db, temp_workspace):
    from littleman.api.routes.onboarding import (
        CompleteBody,
        WelcomeBody,
        complete,
        welcome,
    )

    await welcome(
        WelcomeBody(display_name="A", purpose="Be a research assistant.", model="openai/x"),
        db,
    )
    await complete(CompleteBody(path="custom"), db)
    soul = (temp_workspace / "workspace" / "SOUL.md").read_text()
    assert "research assistant" in soul
    assert "configured conversationally" in soul
    runtime.set_override({"mode": "real"})
