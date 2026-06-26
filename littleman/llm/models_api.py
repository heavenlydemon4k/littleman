"""Live model discovery + connection test for the configured LLM provider.

Powers Settings (populate the model dropdowns, verify the key actually works) and the onboarding
eligibility gate ("is a working model configured?"). The probe is the provider's *models* endpoint
— read-only, **no tokens spent** — so it doubles as a free connection test.

Every call returns an explicit error string on failure (never a silent empty list), per the
project's surface-every-failure rule.
"""

from __future__ import annotations

import httpx

# Curated fallback shown when a live fetch can't run (no key yet) or fails. Full litellm strings.
CURATED: dict[str, list[str]] = {
    "openai": ["openai/gpt-4o", "openai/gpt-4o-mini", "openai/o3-mini"],
    "anthropic": ["anthropic/claude-opus-4-8", "anthropic/claude-sonnet-4-6", "anthropic/claude-haiku-4-5-20251001"],
    "openrouter": ["openrouter/anthropic/claude-sonnet-4-6", "openrouter/openai/gpt-4o"],
    "ollama": ["ollama/llama3.1:8b", "ollama/qwen2.5:14b", "ollama/llama3.3:70b"],
}

# litellm route prefix per provider key.
_PREFIX = {"openai": "openai/", "anthropic": "anthropic/", "openrouter": "openrouter/", "ollama": "ollama/"}


def provider_of(model: str, api_base: str | None) -> str:
    """Infer the provider family from the model string + base URL (best effort)."""
    base = (api_base or "").lower()
    prefix = model.split("/", 1)[0] if "/" in model else ""
    if prefix == "anthropic" or "anthropic.com" in base:
        return "anthropic"
    if prefix == "ollama" or "11434" in base or "ollama" in base:
        return "ollama"
    if prefix == "openrouter" or "openrouter" in base:
        return "openrouter"
    return "openai"  # openai-compatible covers OpenAI, Kimi/Moonshot, and most hosted endpoints


async def fetch_models(provider: str, api_base: str | None, api_key: str | None) -> tuple[list[str], str | None]:
    """Query the provider's models endpoint. Returns (full litellm model ids, error|None)."""
    prefix = _PREFIX.get(provider, "openai/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if provider == "anthropic":
                if not api_key:
                    return [], "no API key set"
                r = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                )
                r.raise_for_status()
                ids = [m["id"] for m in r.json().get("data", [])]
            elif provider == "ollama":
                base = (api_base or "http://localhost:11434").rstrip("/")
                r = await client.get(f"{base}/api/tags")
                r.raise_for_status()
                ids = [m["name"] for m in r.json().get("models", [])]
            else:  # openai-compatible (openai, openrouter, kimi/moonshot, …)
                if not api_base:
                    return [], "no API base URL set"
                if provider != "ollama" and not api_key:
                    return [], "no API key set"
                base = api_base.rstrip("/")
                r = await client.get(f"{base}/models", headers={"Authorization": f"Bearer {api_key}"})
                r.raise_for_status()
                ids = [m["id"] for m in r.json().get("data", [])]
    except httpx.HTTPStatusError as e:
        return [], f"provider returned {e.response.status_code} (check the API key / base URL)"
    except httpx.HTTPError as e:
        return [], f"could not reach provider: {type(e).__name__}"
    except (KeyError, ValueError) as e:
        return [], f"unexpected response from provider: {type(e).__name__}"

    models = sorted({f"{prefix}{i}" if not i.startswith(prefix) else i for i in ids})
    if not models:
        return [], "provider returned no models"
    return models, None


async def list_models(api_base: str | None, api_key: str | None, model_hint: str = "") -> dict:
    """Live models with a curated fallback. Shape: {models, source, error}."""
    from littleman.llm import runtime

    if runtime.active().get("mode") == "fake":
        provider = provider_of(model_hint, api_base)
        return {"models": CURATED.get(provider, []), "source": "fallback", "error": None}

    provider = provider_of(model_hint, api_base)
    models, error = await fetch_models(provider, api_base, api_key)
    if models:
        return {"models": models, "source": "live", "error": None}
    return {"models": CURATED.get(provider, []), "source": "fallback", "error": error}


async def test_connection(api_base: str | None, api_key: str | None, model_hint: str = "") -> dict:
    """Verify the configured provider is reachable and the key works. Shape: {ok, detail}."""
    from littleman.llm import runtime

    if runtime.active().get("mode") == "fake":
        return {"ok": True, "detail": "fake mode — no provider call"}

    provider = provider_of(model_hint, api_base)
    models, error = await fetch_models(provider, api_base, api_key)
    if error:
        return {"ok": False, "detail": error}
    return {"ok": True, "detail": f"{provider}: {len(models)} models available"}
