"""Mental-construct file skills — the agent reads and writes its own cognition.

These let the agent (in a ReAct loop, e.g. during First Light) genuinely read and write its
workspace files, rather than the Python harness doing it on its behalf. They are deliberately
construct-scoped and not a raw filesystem interface: the agent can read a known set of docs and
write only the documents it is allowed to own. SOUL.md and AGENT.md are readable but not
writable here (SOUL is operator/onboarding-owned; AGENT is the platform's fixed operating model).

See docs/design/first-light-and-self-onboarding.md.
"""

from __future__ import annotations

from pathlib import Path

from littleman.config import settings
from littleman.meta import construct

# Static, platform/operator-owned docs that live at the workspace root (read-only here).
_STATIC_DOCS = ("SOUL.md", "AGENT.md", "SKILLS.md")
# Everything the agent may read.
READABLE = set(_STATIC_DOCS) | set(construct.ALL_DOCS)


def _resolve(doc: str) -> Path:
    if doc in construct.ALL_DOCS:
        return construct._doc_path(doc)  # noqa: SLF001 — intentional internal use
    return settings.workspace_dir / doc


def make_construct_skills() -> list[dict]:
    async def read_construct(doc: str) -> dict:
        if doc not in READABLE:
            return {"error": f"unknown doc {doc!r}", "readable": sorted(READABLE)}
        # Prefer the live construct content (handles templates/seeding) for construct docs.
        if doc in construct.ALL_DOCS:
            c = construct.load()
            mapping = {
                "PRIORITIES.md": c.priorities,
                "MACRO_PLAN.md": c.macro_plan,
                "SELF.md": c.self_model,
                "DIRECTIVE.md": c.directive,
                "REFLECTION.md": c.reflection,
            }
            body = mapping.get(doc, "")
            return {"doc": doc, "content": body, "exists": bool(body.strip())}
        p = _resolve(doc)
        if not p.exists():
            return {"doc": doc, "content": "", "exists": False}
        return {"doc": doc, "content": p.read_text(encoding="utf-8"), "exists": True}

    async def write_construct(doc: str, content: str) -> dict:
        if doc not in construct.OVERWRITE_DOCS:
            return {
                "error": f"{doc!r} is not writable here",
                "writable": list(construct.OVERWRITE_DOCS),
                "hint": "REFLECTION.md is append-only (use append_reflection); SOUL.md/AGENT.md are not agent-writable.",
            }
        construct.write_doc(doc, content)
        return {"doc": doc, "written": True, "chars": len(content)}

    async def append_reflection(entry: str) -> dict:
        construct.append_reflection(entry)
        return {"appended": True}

    async def read_template(doc: str) -> dict:
        """Read a construct doc's template (its format + instructions)."""
        if doc not in construct.ALL_DOCS:
            return {"error": f"{doc!r} has no template", "templates": list(construct.ALL_DOCS)}
        return {"doc": doc, "template": construct.read_template(doc)}

    async def list_workspace() -> dict:
        return {
            "readable": sorted(READABLE),
            "writable": list(construct.OVERWRITE_DOCS),
            "append_only": ["REFLECTION.md"],
        }

    return [
        {
            "name": "read_construct",
            "fn": read_construct,
            "description": "Read one of your workspace documents (SOUL.md, AGENT.md, SKILLS.md, or a construct doc).",
            "parameters": {
                "type": "object",
                "properties": {"doc": {"type": "string"}},
                "required": ["doc"],
            },
            "cost": "LOW",
        },
        {
            "name": "write_construct",
            "fn": write_construct,
            "description": "Overwrite one of your construct documents (PRIORITIES.md, MACRO_PLAN.md, SELF.md, DIRECTIVE.md).",
            "parameters": {
                "type": "object",
                "properties": {"doc": {"type": "string"}, "content": {"type": "string"}},
                "required": ["doc", "content"],
            },
            "cost": "LOW",
        },
        {
            "name": "append_reflection",
            "fn": append_reflection,
            "description": "Append a dated entry to your append-only REFLECTION.md.",
            "parameters": {
                "type": "object",
                "properties": {"entry": {"type": "string"}},
                "required": ["entry"],
            },
            "cost": "LOW",
        },
        {
            "name": "read_template",
            "fn": read_template,
            "description": "Read a construct document's template (its required format and instructions).",
            "parameters": {
                "type": "object",
                "properties": {"doc": {"type": "string"}},
                "required": ["doc"],
            },
            "cost": "LOW",
        },
        {
            "name": "list_workspace",
            "fn": list_workspace,
            "description": "List which workspace documents you can read, write, or append to.",
            "parameters": {"type": "object", "properties": {}, "required": []},
            "cost": "LOW",
        },
    ]
