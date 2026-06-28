"""End-to-end tests for the runtime settings API."""

from __future__ import annotations

import pytest

from littleman.config import settings
from littleman.llm import runtime


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "workspace_dir", ws)
    # Start from a blank .env so overrides are the only source of truth in these tests.
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_api_base", "")
    return ws


@pytest.mark.asyncio
async def test_settings_runtime_stores_api_key(temp_workspace, client):
    """PATCH /api/settings/runtime must persist api_key and redact it on GET."""
    r = await client.patch(
        "/api/settings/runtime",
        json={"api_key": "sk-test-12345", "primary_model": "openai/gpt-4o-mini"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["api_key_set"] is True
    assert data["api_key_masked"] != ""
    assert data["primary_model"] == "openai/gpt-4o-mini"

    # The effective runtime config used by LLM calls includes the key.
    cfg = runtime.active()
    assert cfg["api_key"] == "sk-test-12345"
    assert runtime.completion_kwargs()["api_key"] == "sk-test-12345"

    # GET must not leak the raw key.
    r = await client.get("/api/settings/runtime")
    data = r.json()
    assert "api_key" not in data
    assert data["api_key_set"] is True


@pytest.mark.asyncio
async def test_settings_runtime_clears_api_base(temp_workspace, client):
    """Sending an empty api_base should clear a previously set custom base."""
    await client.patch(
        "/api/settings/runtime",
        json={"api_base": "https://api.moonshot.ai/v1"},
    )
    assert runtime.active()["api_base"] == "https://api.moonshot.ai/v1"

    await client.patch("/api/settings/runtime", json={"api_base": ""})
    # Explicit empty override beats the .env default.
    assert runtime.active()["api_base"] == ""


@pytest.mark.asyncio
async def test_settings_runtime_delete_api_key(temp_workspace, client):
    """DELETE /api/settings/runtime/api-key removes the override and reverts to .env."""
    await client.patch("/api/settings/runtime", json={"api_key": "sk-test"})
    assert runtime.active()["api_key"] == "sk-test"

    r = await client.delete("/api/settings/runtime/api-key")
    assert r.status_code == 200
    assert r.json()["api_key_set"] is False
    assert runtime.active()["api_key"] == ""
