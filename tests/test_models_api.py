"""Live model discovery + connection test (Settings / onboarding eligibility).

The probe is read-only (no tokens). Tests cover provider inference, fake-mode short-circuit, and
the fallback-with-surfaced-error path — without any real network call.
"""

import pytest

from littleman.config import settings
from littleman.llm import models_api, runtime


@pytest.fixture
def fake_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_dir", tmp_path / "ws")
    runtime.set_override({"mode": "fake"})
    yield
    runtime.set_override({"mode": "real"})


@pytest.fixture
def real_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_dir", tmp_path / "ws")
    monkeypatch.setattr(runtime, "active", lambda: {"mode": "real", "api_base": "", "api_key": "", "primary_model": ""})
    yield


def test_provider_inference():
    assert models_api.provider_of("anthropic/claude-opus-4-8", None) == "anthropic"
    assert models_api.provider_of("ollama/llama3.1:8b", None) == "ollama"
    assert models_api.provider_of("x", "http://localhost:11434") == "ollama"
    assert models_api.provider_of("openrouter/openai/gpt-4o", None) == "openrouter"
    assert models_api.provider_of("openai/moonshot-v1-128k", "https://api.moonshot.ai/v1") == "openai"


@pytest.mark.asyncio
async def test_test_connection_fake_mode_ok(fake_mode):
    out = await models_api.test_connection("", "", "openai/x")
    assert out["ok"] is True
    assert "fake" in out["detail"]


@pytest.mark.asyncio
async def test_list_models_fake_mode_returns_curated(fake_mode):
    out = await models_api.list_models(None, None, "anthropic/claude-opus-4-8")
    assert out["source"] == "fallback"
    assert out["error"] is None
    assert any("anthropic/" in m for m in out["models"])


@pytest.mark.asyncio
async def test_list_models_falls_back_and_surfaces_error(real_mode, monkeypatch):
    async def boom(*a, **k):
        return [], "provider returned 401 (check the API key / base URL)"

    monkeypatch.setattr(models_api, "fetch_models", boom)
    out = await models_api.list_models("https://api.moonshot.ai/v1", "bad-key", "openai/x")
    assert out["source"] == "fallback"
    assert "401" in out["error"]
    assert out["models"] == models_api.CURATED["openai"]


@pytest.mark.asyncio
async def test_test_connection_reports_failure(real_mode, monkeypatch):
    async def boom(*a, **k):
        return [], "could not reach provider: ConnectError"

    monkeypatch.setattr(models_api, "fetch_models", boom)
    out = await models_api.test_connection("https://x/v1", "k", "openai/x")
    assert out["ok"] is False
    assert "could not reach" in out["detail"]


@pytest.mark.asyncio
async def test_test_connection_ok_when_models_present(real_mode, monkeypatch):
    async def ok(*a, **k):
        return ["openai/m1", "openai/m2"], None

    monkeypatch.setattr(models_api, "fetch_models", ok)
    out = await models_api.test_connection("https://x/v1", "k", "openai/x")
    assert out["ok"] is True
    assert "2 models" in out["detail"]
