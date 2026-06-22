"""Task executor — runs a task tree in dependency order.

Most task types dispatch a registered skill named in their params. EXECUTE tasks (bets) are
special: they never call a skill directly. They are gated through the deterministic risk
governor against the live world-model view, and only then is a position recorded. Live order
signing is stubbed (records intent, status NOT_EXECUTED) until the wallet client is wired —
see littleman/skills/polymarket.py.

Per ADR 0001, execution is serial: one task at a time evaluates against a single consistent
view of capital. Read-only skills may themselves fan out internally, but the executor does not
run EXECUTE tasks concurrently.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from littleman.db.models import Observation, Position
from littleman.macro.risk import RiskGovernor, RiskState
from littleman.meta.world_model import WorldModelManager, WorldModelState
from littleman.skills.registry import SkillRegistry
from littleman.tasks.tree import TaskNode, TaskTree, TaskType


@dataclass
class ExecutionContext:
    db: AsyncSession
    registry: SkillRegistry
    governor: RiskGovernor
    wm: WorldModelManager
    session_id: str


def _risk_state(state: WorldModelState) -> RiskState:
    return RiskState(
        wallet_balance_usdc=Decimal(str(state.wallet_balance_usdc)),
        available_balance_usdc=Decimal(str(state.available_balance_usdc)),
        open_exposure_usdc=Decimal(str(state.open_exposure_usdc())),
        session_start_balance=Decimal(str(state.session_start_balance)),
        peak_balance=Decimal(str(state.peak_balance)),
        exposure_by_category={k: Decimal(str(v)) for k, v in state.exposure_by_category().items()},
        circuit_breaker_active=state.circuit_breaker_active,
    )


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
                    result = await _execute_bet(ctx, node)
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


_REACT_SYSTEM = """You are executing one task for Littleman, an autonomous Polymarket trading
agent. You have skills (tools) available. Use them iteratively to accomplish the objective:
call a skill, read the result, decide the next call, and stop when the objective is met.

Guidelines:
- Prefer reading the knowledge base before fresh web research (read_from_kb / search_kb).
- When researching a market, use scan_markets / get_market / get_orderbook for facts, and
  web_search / browse_url for news and primary sources.
- Persist anything worth keeping for future sessions with write_to_kb.
- For probability work, call estimate_probability with the evidence you gathered.
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


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def _execute_bet(ctx: ExecutionContext, node: TaskNode) -> dict[str, Any]:
    p = node.params
    market_id = p.get("market_id")
    direction = (p.get("direction") or "").upper()
    market_price = _to_float(p.get("market_price"))
    estimated_probability = _to_float(p.get("estimated_probability"))
    category = p.get("category")

    # Refuse to bet without the data a real decision requires — never guess price/edge.
    if not market_id or direction not in ("YES", "NO"):
        return {"status": "NO_BET", "reason": "missing market_id or valid direction"}
    if market_price is None or estimated_probability is None:
        return {
            "status": "NO_BET",
            "reason": "missing market_price or estimated_probability — research first, then bet",
        }

    # Load the live view for sizing and the risk check — single consistent snapshot.
    state = await ctx.wm.load()
    risk_state = _risk_state(state)

    # Size via fractional Kelly unless an explicit size is given.
    if p.get("size_usdc") is not None:
        size = Decimal(str(p["size_usdc"]))
    else:
        size = ctx.governor.size_by_kelly(estimated_probability, market_price, risk_state)

    if size <= 0:
        return {"status": "NO_BET", "reason": "non-positive size after Kelly / no edge"}

    decision = ctx.governor.check_bet(size, risk_state, market_category=category)

    observation = Observation(
        id=str(uuid.uuid4()),
        session_id=ctx.session_id,
        action_type="BET" if decision.allowed else "PASS",
        action_detail={
            "market_id": market_id,
            "direction": direction,
            "size_usdc": float(size),
            "market_price": market_price,
        },
        rationale=p.get("rationale", ""),
        predicted_probability=Decimal(str(estimated_probability)),
        market_price_at_action=Decimal(str(market_price)),
    )
    ctx.db.add(observation)

    if not decision.allowed:
        await ctx.db.commit()
        return {"status": "VETOED", "reason": decision.reason, "size_usdc": float(size)}

    # Record the position. Live signing is stubbed: status PENDING_EXECUTION marks intent.
    position = Position(
        id=str(uuid.uuid4()),
        market_id=market_id,
        market_title=p.get("market_title", market_id),
        direction=direction,
        size_usdc=size,
        entry_price=Decimal(str(market_price)),
        predicted_probability=Decimal(str(estimated_probability)),
        status="OPEN",
        polymarket_order_id=None,
    )
    ctx.db.add(position)

    # Decrement available balance against the committed size.
    new_available = Decimal(str(state.available_balance_usdc)) - size
    await ctx.wm.update(available_balance_usdc=float(new_available))
    await ctx.db.commit()

    return {
        "status": "PLACED",
        "position_id": position.id,
        "size_usdc": float(size),
        "note": "intent recorded; live order signing not yet wired (see polymarket.py)",
    }
