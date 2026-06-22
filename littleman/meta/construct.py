"""The Mental Construct: agent-authored cognitive documents.

These are inspectable markdown files the agent owns and updates. They are loaded into the
system prompt at the start of every session and rewritten by the meta layer at session end.

Documents:
    PRIORITIES.md   — ranked priority stack (overwrite each session)
    MACRO_PLAN.md   — strategic agenda (overwrite when plans shift)
    SELF.md         — runtime self-model: capabilities, calibration, learned patterns
    DIRECTIVE.md    — current session's directive (overwrite each session)
    REFLECTION.md   — append-only learning log

See docs/adr/0001-mental-construct-not-generational-state.md for why these are flat files
with serial (not generational) updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from littleman.config import settings

# Documents that are overwritten wholesale by the agent each time they change.
OVERWRITE_DOCS = ("PRIORITIES.md", "MACRO_PLAN.md", "SELF.md", "DIRECTIVE.md")
# Documents that only ever grow.
APPEND_DOCS = ("REFLECTION.md",)

ALL_DOCS = OVERWRITE_DOCS + APPEND_DOCS


def _construct_dir() -> Path:
    return settings.workspace_dir / "construct"


def _doc_path(name: str) -> Path:
    return _construct_dir() / name


def _template_path(name: str) -> Path:
    stem = name.replace(".md", "")
    return _construct_dir() / f"{stem}.template.md"


@dataclass
class Construct:
    """An in-memory snapshot of the mental construct documents."""

    priorities: str
    macro_plan: str
    self_model: str
    directive: str
    reflection: str

    def as_prompt_block(self, include: tuple[str, ...] = ALL_DOCS) -> str:
        """Render the construct as a block for the system prompt.

        `include` selects which documents to embed (e.g. the directive engine does not need
        the directive that does not exist yet).
        """
        mapping = {
            "PRIORITIES.md": self.priorities,
            "MACRO_PLAN.md": self.macro_plan,
            "SELF.md": self.self_model,
            "DIRECTIVE.md": self.directive,
            "REFLECTION.md": self.reflection,
        }
        parts: list[str] = []
        for name in include:
            body = (mapping.get(name) or "").strip()
            if not body:
                continue
            parts.append(f"===== {name} =====\n{body}")
        return "\n\n".join(parts)


def is_initialised() -> bool:
    """True if the live construct documents exist (i.e. first light has run)."""
    return all(_doc_path(name).exists() for name in OVERWRITE_DOCS)


def load() -> Construct:
    """Load the live construct documents. Missing documents come back empty."""

    def read(name: str) -> str:
        p = _doc_path(name)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    return Construct(
        priorities=read("PRIORITIES.md"),
        macro_plan=read("MACRO_PLAN.md"),
        self_model=read("SELF.md"),
        directive=read("DIRECTIVE.md"),
        reflection=read("REFLECTION.md"),
    )


def read_template(name: str) -> str:
    """Read a document's template (the empty scaffold with format instructions)."""
    p = _template_path(name)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def write_doc(name: str, content: str) -> None:
    """Overwrite a construct document. Used for the OVERWRITE_DOCS."""
    if name not in OVERWRITE_DOCS:
        raise ValueError(f"{name} is not an overwrite document; use append_reflection()")
    _construct_dir().mkdir(parents=True, exist_ok=True)
    _doc_path(name).write_text(content, encoding="utf-8")


def append_reflection(entry: str) -> None:
    """Append an entry to the append-only REFLECTION.md."""
    _construct_dir().mkdir(parents=True, exist_ok=True)
    p = _doc_path("REFLECTION.md")
    existing = p.read_text(encoding="utf-8") if p.exists() else read_template("REFLECTION.md")
    separator = "\n\n" if existing and not existing.endswith("\n\n") else ""
    p.write_text(existing + separator + entry.strip() + "\n", encoding="utf-8")


def seed_from_templates() -> None:
    """Create live documents from their templates if they do not exist yet.

    Called by first light. Does not overwrite documents the agent has already populated.
    """
    _construct_dir().mkdir(parents=True, exist_ok=True)
    for name in ALL_DOCS:
        live = _doc_path(name)
        if live.exists():
            continue
        template = read_template(name)
        live.write_text(template, encoding="utf-8")
