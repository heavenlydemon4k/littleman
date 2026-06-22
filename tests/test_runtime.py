"""Runtime config + autonomous-gating tests.

Guards the safety-critical behaviour: the agent must NOT fire heartbeats on its own unless
autonomous is explicitly enabled.
"""

import pytest

from littleman.config import settings


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_dir", tmp_path / "workspace")
    # Re-import a fresh view each test by clearing any override file.
    return tmp_path


def test_active_defaults_from_settings(temp_workspace):
    from littleman.llm import runtime

    cfg = runtime.active()
    assert cfg["mode"] == settings.llm_mode
    assert cfg["primary_model"] == settings.llm_primary_model
    assert cfg["autonomous"] is False  # safe default


def test_set_override_changes_active(temp_workspace):
    from littleman.llm import runtime

    runtime.set_override({"primary_model": "openai/test-model", "autonomous": True})
    cfg = runtime.active()
    assert cfg["primary_model"] == "openai/test-model"
    assert cfg["autonomous"] is True
    assert runtime.is_autonomous() is True


def test_override_only_applies_known_keys(temp_workspace):
    from littleman.llm import runtime

    runtime.set_override({"primary_model": "openai/x", "bogus": "ignored"})
    assert "bogus" not in runtime.active()


def test_is_autonomous_default_false(temp_workspace):
    from littleman.llm import runtime

    assert runtime.is_autonomous() is False


@pytest.mark.asyncio
async def test_scheduler_tick_skips_when_not_autonomous(temp_workspace):
    # The background tick (force=False) must fire nothing while autonomous is off — and must
    # do so without even touching the database.
    from littleman.heartbeat.scheduler import _tick
    from littleman.llm import runtime

    runtime.set_override({"autonomous": False})
    fired = await _tick(force=False)
    assert fired == 0


def test_set_override_resets_provider_cache(temp_workspace):
    from littleman.llm import provider, runtime

    provider.get_provider()  # populate cache
    runtime.set_override({"mode": "fake"})
    # After override the fake provider is selected.
    from littleman.llm.provider import ScriptedProvider

    assert isinstance(provider.get_provider(), ScriptedProvider)
    runtime.set_override({"mode": "real"})
