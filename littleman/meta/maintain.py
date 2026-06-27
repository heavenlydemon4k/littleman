"""Construct maintenance — the MAINTAIN half of the wake lifecycle.

After execution, the agent's mental workspace must be updated so it does not go stale:

- PRIORITIES.md is re-ranked every wake (always).
- CALENDAR.md is updated with new/pruned events every wake (always).
- SELF.md is conditionally amended when the wake produced a calibration signal or learning.

Without this the construct is a frozen First-Light snapshot rather than a living working
memory. See docs/design/mental-workspace-lifecycle.md.

Skipped in fake mode (offline/tests). Always best-effort: never fails a wake.
"""

from __future__ import annotations

import json
from typing import Any

from littleman.llm import runtime
from littleman.llm.complete import complete_text
from littleman.llm.prompts import (
    CALENDAR_MAINTAIN_SYSTEM,
    PRIORITIES_MAINTAIN_SYSTEM,
    SELF_MAINTAIN_SYSTEM,
    TURNS_MAINTAIN_SYSTEM,
    WORKSPACE_CORE,
)
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


async def _maintain_priorities(c: construct.Construct, directive: dict, summary: str, exec_result: dict) -> bool:
    user = (
        f"{WORKSPACE_CORE}\n\n"
        f"Current PRIORITIES.md:\n{c.priorities or '(empty)'}\n\n"
        f"Current MACRO_PLAN.md:\n{c.macro_plan or '(empty)'}\n\n"
        f"This wake's directive: {json.dumps(directive)}\n"
        f"What happened: {summary}\n"
        f"Skills used: {', '.join(exec_result.get('skills_used', [])) or 'none'}\n"
        f"Failures: {len(exec_result.get('failures', []))}\n\n"
        "Rewrite PRIORITIES.md now, re-ranked to reflect the above."
    )
    body = _strip_fences(await complete_text(PRIORITIES_MAINTAIN_SYSTEM, user, tier="secondary"))
    if body.strip():
        construct.write_doc("PRIORITIES.md", body)
        return True
    return False


async def _maintain_calendar(c: construct.Construct, directive: dict, summary: str, world_state: dict) -> bool:
    """Update CALENDAR.md: add newly discovered events, prune past ones."""
    user = (
        f"{WORKSPACE_CORE}\n\n"
        f"Current CALENDAR.md:\n{c.calendar or '(empty)'}\n\n"
        f"This wake's directive: {json.dumps(directive)}\n"
        f"What happened: {summary}\n"
        f"Open positions and watched markets from world model:\n{json.dumps(world_state)}\n\n"
        "Update CALENDAR.md: add any newly discovered events, remove past ones, keep current ones accurate."
    )
    body = _strip_fences(await complete_text(CALENDAR_MAINTAIN_SYSTEM, user, tier="secondary"))
    if body.strip():
        construct.write_doc("CALENDAR.md", body)
        return True
    return False


async def _maintain_self(c: construct.Construct, directive: dict, summary: str, exec_result: dict) -> bool:
    """Conditionally update SELF.md when the wake produced a calibration signal or lesson."""
    failures = exec_result.get("failures", [])
    bets = exec_result.get("bets_placed", 0)
    # Only invoke the LLM if there is something plausibly worth learning.
    if not failures and bets == 0:
        return False

    failures_text = "\n".join(f"- {f['task']}: {f['error']}" for f in failures) if failures else "none"
    user = (
        f"{WORKSPACE_CORE}\n\n"
        f"Current SELF.md:\n{c.self_model or '(empty)'}\n\n"
        f"This wake's directive: {json.dumps(directive)}\n"
        f"What happened: {summary}\n"
        f"Bets placed: {bets}\n"
        f"Failures:\n{failures_text}\n\n"
        "Decide: did this wake produce something worth recording in SELF.md? "
        "If yes, output the full updated SELF.md. If no, output exactly: NO_UPDATE"
    )
    body = _strip_fences(await complete_text(SELF_MAINTAIN_SYSTEM, user, tier="secondary"))
    if body.strip() and body.strip() != "NO_UPDATE":
        construct.write_doc("SELF.md", body)
        return True
    return False


async def _maintain_turns(c: construct.Construct, directive: dict, summary: str, exec_result: dict) -> bool:
    """Update TURNS.md: roll the execution window forward after the wake."""
    user = (
        f"{WORKSPACE_CORE}\n\n"
        f"Current TURNS.md:\n{c.turns or '(empty)' }\n\n"
        f"This wake's directive: {json.dumps(directive)}\n"
        f"What happened: {summary}\n"
        f"Skills used: {', '.join(exec_result.get('skills_used', [])) or 'none'}\n"
        f"Failures: {len(exec_result.get('failures', []))}\n\n"
        "Update TURNS.md now: move the finished turn to Completed, promote the next Upcoming turn, "
        "and keep the upcoming queue small and concrete."
    )
    body = _strip_fences(await complete_text(TURNS_MAINTAIN_SYSTEM, user, tier="secondary"))
    if body.strip():
        construct.write_doc("TURNS.md", body)
        return True
    return False


def _render_exposure(world_state: dict) -> bool:
    """Render EXPOSURE.md deterministically from the world model. No LLM — runs every mode."""
    from littleman.meta.exposure import render_exposure

    body = render_exposure(world_state or {})
    if body.strip():
        construct.write_doc("EXPOSURE.md", body)
        return True
    return False


async def maintain_construct(
    directive: dict[str, Any],
    session_summary: str,
    exec_result: dict[str, Any],
    world_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Maintain the agent's mental construct after a wake. Returns a status dict.

    Renders EXPOSURE.md (deterministic, every mode), then — outside fake mode — re-ranks
    PRIORITIES.md and CALENDAR.md and conditionally updates SELF.md.
    """
    results: dict[str, Any] = {}

    # EXPOSURE.md is rendered from world state with no LLM call, so it runs in fake mode too.
    try:
        results["exposure"] = _render_exposure(world_state or {})
    except Exception:  # noqa: BLE001
        results["exposure"] = False

    if runtime.active().get("mode") == "fake":
        return {"maintained": any(results.values()), "reason": "fake mode", "docs": results}

    c = construct.load()

    try:
        results["priorities"] = await _maintain_priorities(c, directive, session_summary, exec_result)
    except Exception:  # noqa: BLE001
        results["priorities"] = False

    try:
        results["calendar"] = await _maintain_calendar(
            c, directive, session_summary, world_state or {}
        )
    except Exception:  # noqa: BLE001
        results["calendar"] = False

    try:
        results["self"] = await _maintain_self(c, directive, session_summary, exec_result)
    except Exception:  # noqa: BLE001
        results["self"] = False

    try:
        results["turns"] = await _maintain_turns(c, directive, session_summary, exec_result)
    except Exception:  # noqa: BLE001
        results["turns"] = False

    maintained = any(results.values())
    return {"maintained": maintained, "docs": results}
