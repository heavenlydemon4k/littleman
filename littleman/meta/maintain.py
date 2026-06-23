"""Construct maintenance — the MAINTAIN half of the wake lifecycle.

After execution, the agent's mental workspace must be updated so it does not go stale: the
priority stack is re-ranked to reflect what just happened, and the self-model is amended when
the wake produced a lesson. Without this the construct is a frozen First-Light snapshot rather
than a living working memory. See docs/design/mental-workspace-lifecycle.md.

Skipped in fake mode (offline/tests). Always best-effort: never fails a wake.
"""

from __future__ import annotations

import json
from typing import Any

from littleman.llm import runtime
from littleman.llm.complete import complete_text
from littleman.llm.prompts import PRIORITIES_MAINTAIN_SYSTEM, WORKSPACE_CORE
from littleman.meta import construct


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()


async def maintain_construct(
    directive: dict[str, Any],
    session_summary: str,
    exec_result: dict[str, Any],
) -> dict[str, Any]:
    """Re-rank PRIORITIES.md to reflect this wake. Returns a small status dict."""
    if runtime.active().get("mode") == "fake":
        return {"maintained": False, "reason": "fake mode"}

    c = construct.load()
    user = (
        f"{WORKSPACE_CORE}\n\n"
        f"Current PRIORITIES.md:\n{c.priorities or '(empty)'}\n\n"
        f"Current MACRO_PLAN.md:\n{c.macro_plan or '(empty)'}\n\n"
        f"This wake's directive: {json.dumps(directive)}\n"
        f"What happened: {session_summary}\n"
        f"Skills used: {', '.join(exec_result.get('skills_used', [])) or 'none'}\n"
        f"Failures: {len(exec_result.get('failures', []))}\n\n"
        "Rewrite PRIORITIES.md now, re-ranked to reflect the above."
    )
    try:
        body = _strip_fences(await complete_text(PRIORITIES_MAINTAIN_SYSTEM, user, tier="secondary"))
        if body.strip():
            construct.write_doc("PRIORITIES.md", body)
            return {"maintained": True, "doc": "PRIORITIES.md"}
    except Exception:  # noqa: BLE001 — maintenance must never break a wake
        pass
    return {"maintained": False}
