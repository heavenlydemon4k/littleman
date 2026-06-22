from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Awaitable


@dataclass
class Skill:
    name: str
    fn: Callable[..., Awaitable[Any]]
    description: str
    parameters: dict[str, Any]
    cost: str = "LOW"


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
    ) -> None:
        self._skills[name] = Skill(
            name=name,
            fn=fn,
            description=description,
            parameters=parameters,
            cost=cost,
        )

    async def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        skill = self._skills.get(name)
        if not skill:
            raise ValueError(f"Unknown skill: {name!r}. Available: {list(self._skills)}")
        return await skill.fn(**args)

    def get_definitions(self) -> list[dict]:
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
        ]

    def names(self) -> list[str]:
        return list(self._skills)

    def summary_text(self) -> str:
        lines = []
        for s in self._skills.values():
            lines.append(f"- {s.name}: {s.description} [cost: {s.cost}]")
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

    if db_session_factory:
        for skill in make_probability_skill(db_session_factory):
            registry.register(**skill)

    _registry = registry
    return registry
