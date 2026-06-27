"""The Mental Construct: agent-authored cognitive documents.

These are inspectable markdown files the agent owns and updates. They are loaded into the
system prompt at the start of every session and rewritten by the meta layer at session end.

Documents:
    PRIORITIES.md   — ranked priority stack (overwrite each session)
    MACRO_PLAN.md   — strategic agenda (overwrite when plans shift)
    SELF.md         — runtime self-model: capabilities, calibration, learned patterns
    CALENDAR.md     — upcoming events the agent tracks for self-scheduling
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
OVERWRITE_DOCS = ("PRIORITIES.md", "MACRO_PLAN.md", "SELF.md", "CALENDAR.md", "DIRECTIVE.md")
# Documents that only ever grow.
APPEND_DOCS = ("REFLECTION.md",)
# Documents the agent does NOT author: rendered deterministically from system state each wake
# (EXPOSURE.md is a risk map drawn straight from the world model). Loaded into the prompt and
# readable by the agent, but never LLM-written — so the figures can't drift or hallucinate.
RENDERED_DOCS = ("EXPOSURE.md",)

# Prompt/seed order. EXPOSURE.md sits next to SELF.md so the agent reads its risk state right
# before forming the directive.
ALL_DOCS = (
    "PRIORITIES.md", "MACRO_PLAN.md", "SELF.md", "EXPOSURE.md",
    "CALENDAR.md", "DIRECTIVE.md", "REFLECTION.md",
)

# The subset that must exist for is_initialised() to return True. CALENDAR.md and EXPOSURE.md
# are excluded so workspaces initialized before they were added are not falsely treated as
# uninitialised and re-triggered for First Light.
FIRST_LIGHT_DOCS = ("PRIORITIES.md", "MACRO_PLAN.md", "SELF.md", "DIRECTIVE.md")


_TRUNC_MARKER = "\n…[truncated]…\n"


def _truncate(text: str, limit: int, tail: bool) -> str:
    """Truncate text to `limit` chars, keeping the head (or tail) and marking the cut."""
    if len(text) <= limit:
        return text
    budget = max(limit - len(_TRUNC_MARKER), 0)
    if tail:
        return _TRUNC_MARKER + text[-budget:]
    return text[:budget] + _TRUNC_MARKER


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
    exposure: str
    calendar: str
    directive: str
    reflection: str

    def as_prompt_block(
        self,
        include: tuple[str, ...] = ALL_DOCS,
        per_doc_max: int | None = None,
        total_max: int | None = None,
    ) -> str:
        """Render the construct as a block for the system prompt, within a char budget.

        `include` selects which documents to embed. Each document is capped at `per_doc_max`
        and the whole block at `total_max` (defaults from settings). REFLECTION.md is
        append-only and can grow without bound, so it is truncated to its TAIL (most recent
        entries) rather than its head; other documents keep their head.
        """
        from littleman.config import settings

        per_doc_max = per_doc_max or settings.bootstrap_max_chars
        total_max = total_max or settings.bootstrap_total_max_chars

        mapping = {
            "PRIORITIES.md": self.priorities,
            "MACRO_PLAN.md": self.macro_plan,
            "SELF.md": self.self_model,
            "EXPOSURE.md": self.exposure,
            "CALENDAR.md": self.calendar,
            "DIRECTIVE.md": self.directive,
            "REFLECTION.md": self.reflection,
        }
        parts: list[str] = []
        used = 0
        for name in include:
            body = (mapping.get(name) or "").strip()
            if not body:
                continue
            tail = name == "REFLECTION.md"
            body = _truncate(body, per_doc_max, tail=tail)
            block = f"===== {name} =====\n{body}"
            if used + len(block) > total_max:
                remaining = total_max - used
                if remaining <= 80:  # not enough room for a meaningful slice
                    break
                block = _truncate(block, remaining, tail=False)
            parts.append(block)
            used += len(block)
            if used >= total_max:
                break
        return "\n\n".join(parts)


def is_initialised() -> bool:
    """True if the core construct documents exist (i.e. first light has run).

    Uses FIRST_LIGHT_DOCS rather than OVERWRITE_DOCS so that workspaces initialized before
    CALENDAR.md was added are not incorrectly treated as uninitialised.
    """
    return all(_doc_path(name).exists() for name in FIRST_LIGHT_DOCS)


def load() -> Construct:
    """Load the live construct documents. Missing documents come back empty."""

    def read(name: str) -> str:
        p = _doc_path(name)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    return Construct(
        priorities=read("PRIORITIES.md"),
        macro_plan=read("MACRO_PLAN.md"),
        self_model=read("SELF.md"),
        exposure=read("EXPOSURE.md"),
        calendar=read("CALENDAR.md"),
        directive=read("DIRECTIVE.md"),
        reflection=read("REFLECTION.md"),
    )


def read_template(name: str) -> str:
    """Read a document's template (the empty scaffold with format instructions)."""
    p = _template_path(name)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def write_doc(name: str, content: str) -> None:
    """Overwrite a construct document.

    Valid for the agent-authored OVERWRITE_DOCS and the system-rendered RENDERED_DOCS
    (e.g. EXPOSURE.md, written by the deterministic renderer in maintain).
    """
    if name not in OVERWRITE_DOCS and name not in RENDERED_DOCS:
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


def discover_workspace_files() -> list[tuple[str, str]]:
    """Return (relative_path, content) for markdown/text files in the workspace root.

    Excludes the formal mental construct (handled separately) and gitignored/state paths so the
    prompt block stays focused on agent- or operator-authored documents.
    """
    root = settings.workspace_dir.resolve()
    if not root.exists():
        return []

    excluded = {
        _construct_dir().resolve(),
        (root / "skills").resolve(),
        (root / "state").resolve(),
    }
    files: list[tuple[str, str]] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".md", ".txt"}:
            continue
        try:
            p.relative_to(_construct_dir().resolve())
            continue
        except ValueError:
            pass
        if any(p == e or p.is_relative_to(e) for e in excluded):
            continue
        try:
            rel = p.relative_to(root).as_posix()
            files.append((rel, p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return files


def workspace_prompt_block(max_chars: int | None = None) -> str:
    """Render discovered workspace files as a prompt block, capped by char budget."""
    from littleman.config import settings

    max_chars = max_chars or settings.bootstrap_max_chars
    files = discover_workspace_files()
    if not files:
        return ""

    parts: list[str] = []
    used = 0
    for rel_path, content in files:
        body = content.strip()
        if not body:
            continue
        body = _truncate(body, max_chars, tail=False)
        block = f"===== workspace/{rel_path} =====\n{body}"
        if used + len(block) > max_chars:
            if not parts:
                # Ensure at least a truncated slice of the first file is shown.
                remaining = max(0, max_chars - used)
                block = _truncate(block, remaining, tail=False)
                parts.append(block)
            break
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)
