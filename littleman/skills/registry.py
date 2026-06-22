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
        )

    async def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        skill = self._skills.get(name)
        if not skill:
            raise ValueError(f"Unknown skill: {name!r}. Available: {list(self._skills)}")
        if not skill.available:
            raise ValueError(
                f"Skill {name!r} is unavailable: missing config {skill.requires}"
            )
        return await skill.fn(**args)

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


# Module-level registry, populated by calling build_registry()
_registry: SkillRegistry | None = None


def get_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        raise RuntimeError("Registry not initialised. Call build_registry() first.")
    return _registry


def build_registry(db_session_factory: Any = None) -> SkillRegistry:
    """Construct the registry with all skills wired up to the given DB session factory."""
    from littleman.skills.kb import make_kb_skills
    from littleman.skills.heartbeat import make_heartbeat_skills
    from littleman.skills.web_research import make_web_research_skills
    from littleman.skills.probability import make_probability_skill
    from littleman.skills.polymarket import make_polymarket_skills
    from littleman.skills.polymarket_client import make_account_skills

    global _registry
    registry = SkillRegistry()

    if db_session_factory:
        for skill in make_kb_skills(db_session_factory):
            registry.register(**skill)
        for skill in make_heartbeat_skills(db_session_factory):
            registry.register(**skill)

    for skill in make_web_research_skills():
        registry.register(**skill)
    for skill in make_polymarket_skills():
        registry.register(**skill)
    for skill in make_account_skills():
        registry.register(**skill)

    if db_session_factory:
        for skill in make_probability_skill(db_session_factory):
            registry.register(**skill)

    _registry = registry
    return registry
