"""Generic platform skills available to the default littleman.platform application."""

from __future__ import annotations

from typing import Any, Callable


def make_platform_skills(
    db_session_factory: Callable[[], Any] | None = None,
) -> list[dict[str, Any]]:
    """Return skill definitions for the platform default application."""
    return []
