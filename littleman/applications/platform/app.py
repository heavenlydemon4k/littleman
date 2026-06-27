"""Default platform application — a general-purpose autonomous assistant."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from littleman.applications import Application, register_builtin
from littleman.config import settings


class PlatformApplication(Application):
    """A domain-agnostic assistant application. It is always configured and registers only
    generic platform skills."""

    name = "littleman.platform"

    def is_configured(self) -> bool:
        return True

    def register_skills(
        self,
        registry: Any,
        db_session_factory: Any | None = None,
    ) -> None:
        from littleman.skills.platform import make_platform_skills

        for skill in make_platform_skills(db_session_factory):
            registry.register(**skill)

    async def reconcile(self, db: Any) -> dict[str, Any]:
        return {}

    async def execute(self, ctx: Any, node: Any) -> dict[str, Any]:
        return {"status": "NOOP", "reason": "Platform default has no EXECUTE semantics"}

    def dashboard_status(self) -> dict[str, Any]:
        return {
            "name": "platform",
            "ok": True,
            "detail": f"Running littleman.platform (provider: {settings.llm_primary_model})",
        }

    def root_goal(self) -> dict[str, str]:
        return {
            "title": "Be a helpful, autonomous assistant to the operator",
            "rationale": (
                "Persist what matters, schedule follow-ups, research when useful, and stay "
                "within the operator's guidance."
            ),
        }

    async def first_light_context(self) -> dict[str, Any]:
        return {
            "active_application": self.name,
            "provider": settings.llm_primary_model,
            "utc_now": datetime.now(timezone.utc).isoformat(),
        }


register_builtin("littleman.platform", lambda: PlatformApplication())
