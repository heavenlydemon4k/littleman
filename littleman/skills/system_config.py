"""System configuration skills.

These skills let the assistant inspect and update its own local runtime through
small backend APIs instead of editing arbitrary files. Writes require an explicit
``confirm=True`` argument so the model can propose changes first and the operator
can approve the actual mutation.
"""

from __future__ import annotations

from typing import Any

from littleman.config import settings
from littleman.llm import runtime
from littleman.meta import construct


_RUNTIME_UPDATE_KEYS = {
    "mode",
    "primary_model",
    "secondary_model",
    "api_base",
    "api_key",
    "autonomous",
}


def _soul_path():
    return settings.workspace_dir / "SOUL.md"


def _read_soul() -> str:
    path = _soul_path()
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _redact_runtime(cfg: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(cfg)
    api_key = redacted.pop("api_key", "")
    redacted["api_key_set"] = bool(api_key)
    return redacted


def _construct_summary() -> dict[str, Any]:
    c = construct.load()
    docs = {
        "PRIORITIES.md": c.priorities,
        "MACRO_PLAN.md": c.macro_plan,
        "SELF.md": c.self_model,
        "EXPOSURE.md": c.exposure,
        "CALENDAR.md": c.calendar,
        "DIRECTIVE.md": c.directive,
        "TURNS.md": c.turns,
        "HYPOTHESES.md": c.hypotheses,
        "BLOCKERS.md": c.blockers,
        "SKILL_NOTES.md": c.skill_notes,
        "REFLECTION.md": c.reflection,
    }
    return {
        "initialised": construct.is_initialised(),
        "docs": {
            name: {
                "exists": bool(content.strip()),
                "chars": len(content),
            }
            for name, content in docs.items()
        },
    }


def make_system_config_skills() -> list[dict[str, Any]]:
    async def inspect_system_config(include_soul: bool = False) -> dict[str, Any]:
        """Return the current assistant configuration without exposing secrets."""
        from littleman.applications import get_active_application
        from littleman.skills.registry import get_registry

        app = get_active_application()
        try:
            skill_names = get_registry().names(only_available=False)
        except RuntimeError:
            skill_names = []

        payload: dict[str, Any] = {
            "runtime": _redact_runtime(runtime.active()),
            "workspace_dir": str(settings.workspace_dir),
            "active_application": settings.active_application,
            "application_configured": app.is_configured() if app else False,
            "construct": _construct_summary(),
            "skills": skill_names,
            "soul": {
                "exists": _soul_path().exists(),
                "chars": len(_read_soul()),
            },
        }
        if include_soul:
            payload["soul"]["content"] = _read_soul()
        return payload

    async def propose_soul_update(
        content: str,
        mode: str = "replace",
        rationale: str | None = None,
    ) -> dict[str, Any]:
        """Preview a SOUL.md change without writing it."""
        mode = (mode or "replace").lower()
        if mode not in ("replace", "append", "prepend"):
            return {"ok": False, "error": f"unknown mode: {mode}"}

        existing = _read_soul()
        if mode == "replace":
            proposed = content
        elif mode == "append":
            proposed = existing + ("\n\n" if existing else "") + content
        else:
            proposed = content + ("\n\n" if existing else "") + existing

        return {
            "ok": True,
            "requires_confirmation": True,
            "target": "SOUL.md",
            "mode": mode,
            "rationale": rationale or "",
            "current_chars": len(existing),
            "proposed_chars": len(proposed),
            "proposed_content": proposed,
        }

    async def apply_soul_update(
        content: str,
        mode: str = "replace",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Apply a confirmed SOUL.md update."""
        if not confirm:
            return {
                "updated": False,
                "requires_confirmation": True,
                "reason": "call propose_soul_update first, then call this with confirm=true",
            }

        proposed = await propose_soul_update(content=content, mode=mode)
        if not proposed.get("ok"):
            return {"updated": False, "reason": proposed.get("error", "invalid update")}

        path = _soul_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(proposed["proposed_content"], encoding="utf-8")
        return {
            "updated": True,
            "target": "SOUL.md",
            "mode": proposed["mode"],
            "bytes": len(proposed["proposed_content"].encode("utf-8")),
        }

    async def set_runtime_config(
        values: dict[str, Any],
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Apply confirmed runtime config values."""
        if not confirm:
            return {
                "updated": False,
                "requires_confirmation": True,
                "reason": "runtime changes require confirm=true",
                "allowed_keys": sorted(_RUNTIME_UPDATE_KEYS),
            }

        clean = {k: v for k, v in values.items() if k in _RUNTIME_UPDATE_KEYS}
        ignored = sorted(k for k in values if k not in _RUNTIME_UPDATE_KEYS)
        if not clean:
            return {
                "updated": False,
                "reason": "no supported runtime keys provided",
                "ignored": ignored,
            }
        updated = runtime.set_override(clean)
        return {
            "updated": True,
            "runtime": _redact_runtime(updated),
            "changed": sorted(clean),
            "ignored": ignored,
        }

    return [
        {
            "name": "inspect_system_config",
            "fn": inspect_system_config,
            "description": (
                "Inspect the current Littleman runtime, identity, active application, "
                "construct status, and registered skills. Secrets are redacted."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "include_soul": {
                        "type": "boolean",
                        "description": "Include SOUL.md content in the response.",
                    }
                },
                "required": [],
            },
            "cost": "LOW",
            "chat_safe": True,
        },
        {
            "name": "propose_soul_update",
            "fn": propose_soul_update,
            "description": (
                "Preview a change to SOUL.md without writing it. Use this before "
                "applying identity or purpose changes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "mode": {"type": "string", "enum": ["replace", "append", "prepend"]},
                    "rationale": {"type": "string"},
                },
                "required": ["content"],
            },
            "cost": "LOW",
            "chat_safe": True,
        },
        {
            "name": "apply_soul_update",
            "fn": apply_soul_update,
            "description": (
                "Apply a confirmed SOUL.md update. Requires confirm=true and should "
                "only be called after the operator approves the proposed content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "mode": {"type": "string", "enum": ["replace", "append", "prepend"]},
                    "confirm": {"type": "boolean"},
                },
                "required": ["content", "confirm"],
            },
            "cost": "LOW",
            "chat_safe": True,
        },
        {
            "name": "set_runtime_config",
            "fn": set_runtime_config,
            "description": (
                "Apply confirmed runtime settings such as model, API base, mode, or "
                "autonomous toggle. Requires confirm=true."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "values": {
                        "type": "object",
                        "description": (
                            "Runtime keys to set: mode, primary_model, secondary_model, "
                            "api_base, api_key, autonomous."
                        ),
                    },
                    "confirm": {"type": "boolean"},
                },
                "required": ["values", "confirm"],
            },
            "cost": "LOW",
            "chat_safe": True,
        },
    ]
