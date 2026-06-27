from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from littleman.config import settings

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
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
            item = line.strip()[1:].strip().strip('"').strip("'")
            if key not in meta or not isinstance(meta[key], list):
                meta[key] = []
            meta[key].append(item)
    return meta, body


class SkillDocIndex:
    """Map registered skill names to their documentation files."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._name_to_doc: dict[str, Path] = {}
        self._build()

    def _build(self) -> None:
        if not self.skills_dir.exists():
            return
        for path in sorted(self.skills_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(text)
            # A doc with a `skills:` list covers those registered names.
            covered = meta.get("skills") or [path.stem]
            if isinstance(covered, str):
                covered = [covered]
            for name in covered:
                self._name_to_doc[name] = path

    def doc_for(self, name: str) -> Path | None:
        return self._name_to_doc.get(name)

    def available_names(self) -> list[str]:
        return sorted(self._name_to_doc)


async def read_skill_doc(name: str) -> str:
    """Read the detailed documentation for a named skill.

    `name` is the registered skill name (e.g. `write_to_kb`). The doc file is looked up via the
    `skills:` frontmatter list, falling back to a file named after the skill.
    """
    doc_dir = Path(settings.workspace_dir) / "skills"
    index = SkillDocIndex(doc_dir)
    path = index.doc_for(name)
    if path is not None and path.exists():
        return path.read_text(encoding="utf-8")

    # Legacy fallback: exact file name.
    for ext in (".md", ".txt"):
        p = doc_dir / f"{name}{ext}"
        if p.exists():
            return p.read_text(encoding="utf-8")

    available = index.available_names()
    hint = f" Available: {', '.join(available)}" if available else ""
    return f"No documentation found for skill '{name}'.{hint}"
