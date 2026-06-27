"""Application plug-in interface.

A littleman *application* is a domain-specific bundle: a SOUL.md identity, a skill pack,
and optional runtime hooks (reconcile, EXECUTE-task handling, dashboard status). The platform
core is intentionally application-agnostic; this module is the seam where applications attach.

The active application is selected via `settings.active_application`. Its name should match the
name returned by the application's `name` attribute. Discovery is simple: the platform knows
about built-in applications listed in `BUILTIN_APPLICATIONS`; future versions may scan
`workspace/applications/` or installed packages.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol, runtime_checkable


@runtime_checkable
class Application(Protocol):
    """Contract for a littleman application."""

    name: str

    def is_configured(self) -> bool:
        """Return True if the required config/credentials for this app are present."""
        ...

    def register_skills(
        self,
        registry: Any,
        db_session_factory: Callable[[], Awaitable[Any]] | None = None,
    ) -> None:
        """Add application-specific skills to the registry."""
        ...

    async def reconcile(self, db: Any) -> dict[str, Any]:
        """Optional pre-session hook to refresh external state into the world model."""
        ...

    async def execute(self, ctx: Any, node: Any) -> dict[str, Any]:
        """Handle an EXECUTE-type task node. Return a result dict."""
        ...

    def dashboard_status(self) -> dict[str, Any]:
        """Return connection/status information shown on the agent dashboard."""
        ...

    def root_goal(self) -> dict[str, str]:
        """Return the default root goal for the goal tree."""
        ...


BUILTIN_APPLICATIONS: dict[str, Callable[[], Application]] = {}


def register_builtin(name: str, factory: Callable[[], Application]) -> None:
    BUILTIN_APPLICATIONS[name] = factory


def load_application(name: str) -> Application | None:
    """Load a built-in application by name. Returns None if unknown."""
    factory = BUILTIN_APPLICATIONS.get(name)
    return factory() if factory else None


def get_active_application() -> Application | None:
    from littleman.config import settings

    return load_application(settings.active_application)
