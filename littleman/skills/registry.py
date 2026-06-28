from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class Skill:
    name: str
    fn: Callable[..., Awaitable[Any]]
    description: str
    parameters: dict[str, Any]
    cost: str = "LOW"
    requires: list[str] = field(default_factory=list)
    available: bool = True
    chat_safe: bool = True


def _requirements_met(requires: list[str]) -> bool:
    """A skill is available only if every required settings field is non-empty.

    Mirrors OpenClaw's skill gating (metadata.openclaw required env/binaries): a skill whose
    backing credential is missing should not be offered to the model, so the agent's
    self-model reflects what it can actually do.
    """
    from littleman.config import settings

    for field_name in requires:
        if not getattr(settings, field_name, None):
            return False
    return True


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(
        self,
        name: str,
        fn: Callable[..., Awaitable[Any]],
        description: str,
        parameters: dict[str, Any],
        cost: str = "LOW",
        requires: list[str] | None = None,
        chat_safe: bool = True,
    ) -> None:
        requires = requires or []
        self._skills[name] = Skill(
            name=name,
            fn=fn,
            description=description,
            parameters=parameters,
            cost=cost,
            requires=requires,
            available=_requirements_met(requires),
            chat_safe=chat_safe,
        )

    async def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        skill = self._skills.get(name)
        if not skill:
            raise ValueError(f"Unknown skill: {name!r}. Available: {list(self._skills)}")
        if not skill.available:
            raise ValueError(
                f"Skill {name!r} is unavailable: missing config {skill.requires}"
            )

        # Surface the call to the live action feed (no-op outside a wake; never raises).
        from littleman.agent import events

        await events.emit(
            events.TOOL_CALL,
            {"name": name, "cost": skill.cost, "args": events.shrink(args)},
        )
        try:
            result = await skill.fn(**args)
        except Exception as e:  # noqa: BLE001 — report the failure, then re-raise unchanged
            await events.emit(events.TOOL_RESULT, {"name": name, "ok": False, "error": str(e)})
            raise
        await events.emit(
            events.TOOL_RESULT, {"name": name, "ok": True, "summary": events.shrink(result)}
        )
        return result

    def get_definitions(self, only_available: bool = True) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": s.parameters,
                },
            }
            for s in self._skills.values()
            if s.available or not only_available
        ]

    def get_chat_definitions(self, only_available: bool = True) -> list[dict]:
        """Tool definitions limited to skills that are safe for interactive chat use."""
        return [
            {
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": s.parameters,
                },
            }
            for s in self._skills.values()
            if (s.available or not only_available) and s.chat_safe
        ]

    def names(self, only_available: bool = True) -> list[str]:
        return [s.name for s in self._skills.values() if s.available or not only_available]

    def summary_text(self) -> str:
        """Capability inventory for the self-model — flags unavailable skills explicitly."""
        lines = []
        for s in self._skills.values():
            if s.available:
                lines.append(f"- {s.name}: {s.description} [cost: {s.cost}]")
            else:
                lines.append(
                    f"- {s.name}: {s.description} [UNAVAILABLE — needs {', '.join(s.requires)}]"
                )
        return "\n".join(lines)

    def subset(self, names: set[str]) -> "SkillRegistry":
        """Return a new registry containing only the named skills."""
        new = SkillRegistry()
        for name in names:
            skill = self._skills.get(name)
            if skill is not None:
                new._skills[name] = skill
        return new


# Module-level registry, populated by calling build_registry()
_registry: SkillRegistry | None = None


def get_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        raise RuntimeError("Registry not initialised. Call build_registry() first.")
    return _registry


def build_registry(db_session_factory: Any = None) -> SkillRegistry:
    """Construct the registry with all skills wired up to the given DB session factory."""
    # Import built-in applications so they register themselves.
    import littleman.applications.platform  # noqa: F401

    from littleman.applications import get_active_application
    from littleman.skills.kb import make_kb_skills
    from littleman.skills.heartbeat import make_heartbeat_skills
    from littleman.skills.web_research import make_web_research_skills
    from littleman.skills.probability import make_probability_skill
    from littleman.skills.skill_docs import read_skill_doc
    from littleman.skills.construct_skills import make_construct_skills
    from littleman.skills.workspace_files import make_workspace_file_skills
    from littleman.skills.update_self import make_update_self_skill
    from littleman.skills.openclaw_loader import load_openclaw_skills
    from littleman.skills.calibration import make_calibration_skills
    from littleman.skills.system_config import make_system_config_skills

    global _registry
    registry = SkillRegistry()

    # OpenClaw-style filesystem skills (optional, separate directory). Load these first so
    # every built-in skill registered afterwards overwrites any OpenClaw manifest of the
    # same name.
    for skill in load_openclaw_skills():
        registry.register(**skill)

    # On-demand skill documentation — always available; zero cost.
    registry.register(
        name="read_skill_doc",
        fn=read_skill_doc,
        description=(
            "Read the detailed documentation for a named skill before using it. "
            "Call this first when you need guidance on how to use a specific skill effectively."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "Skill name, e.g. 'web_research', 'probability', "
                        "'polymarket_scan', 'polymarket_orderbook', 'kb', 'heartbeat'"
                    ),
                }
            },
            "required": ["name"],
        },
        cost="LOW",
    )

    if db_session_factory:
        for skill in make_kb_skills(db_session_factory):
            registry.register(**skill)
        for skill in make_heartbeat_skills(db_session_factory):
            registry.register(**skill)
        for skill in make_update_self_skill(db_session_factory):
            registry.register(**skill)
        for skill in make_calibration_skills(db_session_factory):
            registry.register(**skill)

    for skill in make_web_research_skills():
        registry.register(**skill)

    for skill in make_system_config_skills():
        registry.register(**skill)

    application = get_active_application()
    if application:
        application.register_skills(registry, db_session_factory)

    # Platform / workspace skills.
    for skill in make_construct_skills():
        registry.register(**skill)

    for skill in make_workspace_file_skills():
        registry.register(**skill)


    if db_session_factory:
        for skill in make_probability_skill(db_session_factory):
            registry.register(**skill)

    _registry = registry
    return registry
