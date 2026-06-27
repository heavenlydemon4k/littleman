"""Task executor — runs a task tree in dependency order.

Most task types dispatch a registered skill named in their params. EXECUTE tasks are handled
by the active application (e.g. placing a bet for a trading application), which is
responsible for any domain-specific gating and state recording.

Per ADR 0001, execution is serial: one task at a time evaluates against a single consistent
view. Read-only skills may themselves fan out internally, but the executor does not run EXECUTE
tasks concurrently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from littleman.macro.risk import RiskGovernor
from littleman.meta.world_model import WorldModelManager
from littleman.skills.registry import SkillRegistry
from littleman.tasks.tree import TaskNode, TaskTree, TaskType


@dataclass
class ExecutionContext:
    db: AsyncSession
    registry: SkillRegistry
    governor: RiskGovernor
    wm: WorldModelManager
    session_id: str


async def run_tree(ctx: ExecutionContext, tree: TaskTree) -> dict[str, Any]:
    """Execute all ready tasks until the tree is complete."""
    bets_placed = 0
    research_calls = 0
    skills_used: list[str] = []
    failures: list[dict[str, str]] = []

    while not tree.is_complete():
        ready = tree.get_ready()
        if not ready:
            break  # remaining tasks are blocked by failed dependencies
        for node in ready:
            tree.mark_running(node.id)
            try:
                if node.type == TaskType.EXECUTE:
                    result = await _execute_application(ctx, node)
                    if result.get("status") == "PLACED":
                        bets_placed += 1
                else:
                    result = await _dispatch_skill(ctx, node)
                    if node.type == TaskType.RESEARCH:
                        research_calls += 1
                if node.params.get("skill"):
                    skills_used.append(node.params["skill"])
                if isinstance(result, dict):
                    skills_used.extend(result.get("skills_used", []))
                tree.mark_done(node.id, result)
            except Exception as e:  # noqa: BLE001 — one task's failure must not crash the session
                failures.append({"task": node.title, "error": str(e)})
                tree.mark_failed(node.id, str(e))

    return {
        "bets_placed": bets_placed,
        "research_calls": research_calls,
        "skills_used": skills_used,
        "failures": failures,
        "tree": tree.summary(),
    }


_REACT_SYSTEM = """You are executing one task for Littleman, an autonomous agent. You have
skills (tools) available. Use them iteratively to accomplish the objective: call a skill, read
the result, decide the next call, and stop when the objective is met.

Guidelines:
- Prefer reading the knowledge base before fresh web research (read_from_kb / search_kb).
- Use whatever skills are relevant to the task; check read_skill_doc if you are unsure.
- Persist anything worth keeping for future sessions with write_to_kb.
- Be economical: a handful of focused tool calls, not exhaustive crawling.
When done, reply with a concise plain-text summary of what you found or did."""


async def _dispatch_skill(ctx: ExecutionContext, node: TaskNode) -> Any:
    # Direct single-skill dispatch when the task names one explicitly.
    skill = node.params.get("skill")
    if skill:
        return await ctx.registry.dispatch(skill, node.params.get("args", {}))

    # Agentic (ReAct) execution when the task carries a natural-language objective: the agent
    # iteratively chooses and calls real skills to accomplish it.
    objective = node.params.get("objective")
    if objective:
        from littleman.agent.loop import run as react_run

        loop = await react_run(
            _REACT_SYSTEM,
            f"Objective: {objective}\n\nTask: {node.title}",
            ctx.registry,
            max_iterations=4,
        )
        skills = [t["name"] for t in loop.tool_invocations]

        # Guarantee findings persist: if the agent didn't write to the KB itself, store its
        # summary so the research is available to future sessions.
        if "write_to_kb" not in skills and loop.final_text.strip():
            try:
                await ctx.registry.dispatch(
                    "write_to_kb",
                    {
                        "topic": node.title,
                        "content": loop.final_text.strip(),
                        "confidence": "MEDIUM",
                        "expires_hours": 24,
                    },
                )
                skills.append("write_to_kb")
            except Exception:  # noqa: BLE001 — persistence is best-effort
                pass

        return {
            "objective": objective,
            "summary": loop.final_text,
            "skills_used": skills,
            "iterations": loop.iterations,
        }

    return {"note": "no skill or objective specified", "params": node.params}


async def _execute_application(ctx: ExecutionContext, node: TaskNode) -> dict[str, Any]:
    """Dispatch an EXECUTE task to the active application, if one is loaded."""
    from littleman.applications import get_active_application

    app = get_active_application()
    if app is None:
        return {
            "status": "NO_EXECUTE",
            "reason": "no active application configured to handle EXECUTE tasks",
        }
    return await app.execute(ctx, node)
