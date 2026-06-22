"""Runtime LLM + autonomy config — the single source of truth the agent actually uses.

`.env` (via settings) provides defaults. A small JSON override file (workspace/state/
runtime.json), editable live from the UI, overlays them — so you can change the model, switch
real/fake, or toggle autonomous mode without restarting or editing .env.

Critically: `autonomous` defaults to FALSE. The background scheduler refuses to fire heartbeats
unless it is true, so the agent never burns tokens on its own. Manual runs (UI buttons / CLI
boot|once) are always allowed regardless — they are explicit user actions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from littleman.config import settings

_OVERRIDE_KEYS = ("mode", "primary_model", "secondary_model", "api_base", "api_key", "autonomous")


def _override_path() -> Path:
    state = settings.workspace_dir / "state"
    state.mkdir(parents=True, exist_ok=True)
    return state / "runtime.json"


def _read_override() -> dict[str, Any]:
    p = _override_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def active() -> dict[str, Any]:
    """Effective runtime config: .env defaults overlaid with the live override file."""
    base = {
        "mode": settings.llm_mode,
        "primary_model": settings.llm_primary_model,
        "secondary_model": settings.llm_secondary_model,
        "api_base": settings.llm_api_base,
        "api_key": settings.llm_api_key,
        "autonomous": False,
    }
    override = _read_override()
    for k in _OVERRIDE_KEYS:
        if k in override and override[k] not in (None, ""):
            base[k] = override[k]
    return base


def set_override(values: dict[str, Any]) -> dict[str, Any]:
    """Persist a partial override and reset the provider cache so changes take effect."""
    current = _read_override()
    for k, v in values.items():
        if k in _OVERRIDE_KEYS:
            current[k] = v
    _override_path().write_text(json.dumps(current, indent=2), encoding="utf-8")

    # Provider mode may have changed — drop cached providers.
    from littleman.llm import provider

    provider.reset_cache()
    return active()


def model_for(tier: str) -> str:
    cfg = active()
    return cfg["secondary_model"] if tier == "secondary" else cfg["primary_model"]


def completion_kwargs() -> dict[str, Any]:
    cfg = active()
    kwargs: dict[str, Any] = {}
    if cfg.get("api_base"):
        kwargs["api_base"] = cfg["api_base"]
    if cfg.get("api_key"):
        kwargs["api_key"] = cfg["api_key"]
    return kwargs


def is_autonomous() -> bool:
    return bool(active().get("autonomous"))
