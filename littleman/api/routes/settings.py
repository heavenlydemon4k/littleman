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
