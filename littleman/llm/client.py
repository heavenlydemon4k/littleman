from pathlib import Path

from littleman.config import settings


def load_soul() -> str:
    soul_path = settings.workspace_dir / "SOUL.md"
    if soul_path.exists():
        return soul_path.read_text(encoding="utf-8")
    return "You are Littleman, an autonomous agent on the littleman platform."


def load_agent_manual() -> str:
    """The platform operating manual (AGENT.md) — how a littleman agent works."""
    p = settings.workspace_dir / "AGENT.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def build_tool_definitions() -> list[dict]:
    """Return the current registry's tool definitions, or an empty list if not built.

    Chat uses this as a fallback when no wake has initialised the registry yet. It no longer
    hard-codes application-specific tools; whatever skills are registered (platform + active
    application) are what the model sees.
    """
    try:
        from littleman.skills.registry import get_registry

        return get_registry().get_definitions()
    except RuntimeError:
        return []
