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
                tree.mark_done(node.id, result)
            except Exception as e:  # noqa: BLE001 — one task's failure must not crash the session
                tree.mark_failed(node.id, str(e))

    return {"bets_placed": bets_placed, "research_calls": research_calls, "tree": tree.summary()}


async def _dispatch_skill(ctx: ExecutionContext, node: TaskNode) -> Any:
    skill = node.params.get("skill")
    args = node.params.get("args", {})
    if not skill:
        return {"note": "no skill specified; task is a reasoning placeholder", "params": node.params}
    return await ctx.registry.dispatch(skill, args)


async def _execute_bet(ctx: ExecutionContext, node: TaskNode) -> dict[str, Any]:
    p = node.params
    market_id = p["market_id"]
    direction = p["direction"]
    market_price = float(p.get("market_price", 0.5))
    estimated_probability = float(p.get("estimated_probability", market_price))
    category = p.get("category")

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
