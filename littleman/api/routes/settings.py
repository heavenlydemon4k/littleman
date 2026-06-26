from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/settings", tags=["settings"])


class RuntimeUpdate(BaseModel):
    mode: str | None = None             # "real" | "fake"
    primary_model: str | None = None
    secondary_model: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    autonomous: bool | None = None


class ProviderProbe(BaseModel):
    """Optional overrides so the UI can list/test a key+base before saving them."""
    api_base: str | None = None
    api_key: str | None = None
    model_hint: str | None = None


def _probe_creds(body: ProviderProbe | None) -> tuple[str | None, str | None, str]:
    """Resolve effective base/key/model: explicit overrides win, else the live runtime config."""
    from littleman.llm import runtime

    cfg = runtime.active()
    api_base = body.api_base if body and body.api_base else cfg["api_base"]
    api_key = body.api_key if body and body.api_key else cfg["api_key"]
    model_hint = (body.model_hint if body and body.model_hint else cfg["primary_model"]) or ""
    return api_base, api_key, model_hint


@router.get("/runtime")
async def get_runtime():
    """Effective agent runtime config (LLM + autonomy) — the single source of truth the agent
    and the interactive chat both use."""
    from littleman.llm import runtime

    cfg = runtime.active()
    key = cfg.get("api_key") or ""
    return {
        "mode": cfg["mode"],
        "primary_model": cfg["primary_model"],
        "secondary_model": cfg["secondary_model"],
        "api_base": cfg["api_base"],
        "api_key_set": bool(key),
        "api_key_masked": (key[:5] + "…" + key[-4:]) if len(key) > 12 else ("set" if key else ""),
        "autonomous": cfg["autonomous"],
    }


@router.patch("/runtime")
async def update_runtime(body: RuntimeUpdate):
    """Live-update the agent's LLM/autonomy config without a restart."""
    from littleman.llm import runtime

    values = {k: v for k, v in body.model_dump().items() if v is not None}
    runtime.set_override(values)
    return await get_runtime()


@router.delete("/runtime/api-key")
async def delete_runtime_api_key():
    """Clear a UI-pasted API key from the live override (revert to the .env default)."""
    from littleman.llm import runtime

    runtime.remove_override(["api_key"])
    return await get_runtime()


@router.post("/models")
async def list_models(body: ProviderProbe | None = None):
    """Available models for the configured (or supplied) provider — live, with curated fallback.

    Read-only against the provider's models endpoint; spends no tokens. Accepts optional
    base/key overrides so the UI can populate the dropdown before the key is saved."""
    from littleman.llm import models_api

    api_base, api_key, model_hint = _probe_creds(body)
    return await models_api.list_models(api_base, api_key, model_hint)


@router.post("/test-connection")
async def test_connection(body: ProviderProbe | None = None):
    """Verify the configured (or supplied) LLM provider is reachable and the key works.

    This is the probe the onboarding eligibility gate uses. Returns {ok, detail}."""
    from littleman.llm import models_api

    api_base, api_key, model_hint = _probe_creds(body)
    return await models_api.test_connection(api_base, api_key, model_hint)
