"""OpenClaw / AgentSkills filesystem loader.

Skills dropped into `workspace/openclaw/skills/*.md` as `SKILL.md` manifests (YAML frontmatter
with `name` + `description`) are registered alongside the built-in Python skills. If a matching
Python implementation exists at `littleman.skills.openclaw.<name>`, it is wired up; otherwise
the manifest is ignored unless it explicitly sets `register: true` (in which case it dispatches
a helpful unimplemented error).

This lets littleman import skills from OpenClaw's marketplace format without changing the
platform's core Python registry.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Any, Awaitable, Callable

from littleman.config import settings


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from markdown body."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    yaml_text, body = match.groups()
    meta: dict[str, Any] = {}
    key: str | None = None
    for line in yaml_text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            meta[key] = value
        elif key is not None and line.strip().startswith("-"):
            # Minimal list support for requires, etc.
            item = line.strip()[1:].strip().strip('"').strip("'")
            if key not in meta or not isinstance(meta[key], list):
                meta[key] = []
            meta[key].append(item)
    return meta, body


def _load_impl(name: str) -> Callable[..., Awaitable[Any]] | None:
    """Try to import littleman.skills.openclaw.<name>.<name> as the implementation."""
    module_path = f"littleman.skills.openclaw.{name}"
    try:
        module = importlib.import_module(module_path)
    except ImportError:
        return None
    return getattr(module, name, None)


_SKILL_DIR = "openclaw/skills"


def load_openclaw_skills() -> list[dict[str, Any]]:
    """Scan workspace/openclaw/skills/*.md for executable skill manifests."""
    skills_dir = settings.workspace_dir / _SKILL_DIR
    if not skills_dir.exists():
        return []

    skills: list[dict[str, Any]] = []
    for path in sorted(skills_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        name = meta.get("name") or path.stem
        description = meta.get("description") or _first_paragraph(body) or f"Filesystem skill: {name}"
        cost = meta.get("cost", "LOW")
        requires = meta.get("requires", [])
        if isinstance(requires, str):
            requires = [r.strip() for r in requires.split(",") if r.strip()]

        parameters = meta.get("parameters") or {
            "type": "object",
            "properties": {},
            "required": [],
        }

        impl = _load_impl(name)
        register = meta.get("register", impl is not None)
        if not register:
            continue
        if impl is None:
            impl = _make_unimplemented(name)

        skills.append(
            {
                "name": name,
                "fn": impl,
                "description": description,
                "parameters": parameters,
                "cost": cost,
                "requires": requires,
            }
        )
    return skills


def _first_paragraph(text: str) -> str:
    """Return the first non-empty paragraph of markdown text."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
            return stripped
    return ""


def _make_unimplemented(name: str) -> Callable[..., Awaitable[dict[str, Any]]]:
    async def unimplemented(**kwargs: Any) -> dict[str, Any]:
        return {
            "error": (
                f"Skill {name!r} is loaded from a SKILL.md manifest but has no Python "
                f"implementation. Create littleman/skills/openclaw/{name}.py with an async "
                f"function named {name!r}."
            )
        }

    return unimplemented
