"""Agent observability + control routes.

Surfaces the running agent's state to the frontend dashboard: the heartbeat schedule, session
history, world model, exposure, goal tree, and the mental construct. Also exposes controls to
boot (First Light) and trigger a single session.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from littleman.db.connection import get_db
from littleman.db.models import AgentSession, Heartbeat, Position, Strategy
from littleman.meta import construct
from littleman.meta.world_model import WorldModelManager

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db)):
    wm = await WorldModelManager(db).load()
    scheduled = await db.execute(
        select(Heartbeat).where(Heartbeat.status == "SCHEDULED").order_by(Heartbeat.fire_at)
    )
    next_hb = scheduled.scalars().first()
    last_session = await db.execute(
        select(AgentSession).order_by(desc(AgentSession.started_at)).limit(1)
    )
    last = last_session.scalar_one_or_none()
    return {
        "initialised": construct.is_initialised(),
        "wallet_balance_usdc": wm.wallet_balance_usdc,
        "available_balance_usdc": wm.available_balance_usdc,
        "total_pnl": wm.total_pnl,
        "open_positions": len(wm.open_positions),
        "open_exposure_usdc": wm.open_exposure_usdc(),
        "circuit_breaker_active": wm.circuit_breaker_active,
        "next_heartbeat": {
            "fire_at": next_hb.fire_at.isoformat() if next_hb else None,
            "reason": next_hb.reason if next_hb else None,
            "session_type": next_hb.session_type if next_hb else None,
        } if next_hb else None,
        "last_session": {
            "summary": last.outcome_summary,
            "started_at": last.started_at.isoformat() if last and last.started_at else None,
        } if last else None,
    }


@router.get("/heartbeats")
async def heartbeats(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Heartbeat).order_by(desc(Heartbeat.fire_at)).limit(limit))
    rows = result.scalars().all()
    return [
        {
            "id": h.id,
            "fire_at": h.fire_at.isoformat() if h.fire_at else None,
            "reason": h.reason,
            "session_type": h.session_type,
            "status": h.status,
            "spawned_by": h.spawned_by,
            "context": h.context,
        }
        for h in rows
    ]


@router.get("/sessions")
async def sessions(limit: int = 30, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentSession).order_by(desc(AgentSession.started_at)).limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": s.id,
            "heartbeat_id": s.heartbeat_id,
            "directive": s.directive,
            "bets_placed": s.bets_placed,
            "research_calls": s.research_calls,
            "heartbeats_created": s.heartbeats_created,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "outcome_summary": s.outcome_summary,
        }
        for s in rows
    ]


@router.get("/positions")
async def positions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Position).order_by(desc(Position.placed_at)))
    rows = result.scalars().all()
    return [
        {
            "id": p.id,
            "market_title": p.market_title,
            "direction": p.direction,
            "size_usdc": float(p.size_usdc),
            "entry_price": float(p.entry_price),
            "predicted_probability": float(p.predicted_probability),
            "status": p.status,
            "outcome": p.outcome,
            "pnl": float(p.pnl) if p.pnl is not None else None,
        }
        for p in rows
    ]


@router.get("/goal-tree")
async def goal_tree(db: AsyncSession = Depends(get_db)):
    from littleman.macro.goal_tree import get_tree_as_dict

    return await get_tree_as_dict(db)


@router.get("/construct")
async def get_construct():
    """The mental construct documents, for inline display on the dashboard."""
    c = construct.load()
    return {
        "initialised": construct.is_initialised(),
        "documents": {
            "PRIORITIES.md": c.priorities,
            "MACRO_PLAN.md": c.macro_plan,
            "SELF.md": c.self_model,
            "DIRECTIVE.md": c.directive,
            "REFLECTION.md": c.reflection,
        },
    }


# ── Controls ──────────────────────────────────────────────────────────────────

@router.post("/boot")
async def boot():
    """Run First Light (idempotent unless forced) and schedule the first heartbeat."""
    from littleman.agent.session import run_session

    result = await run_session(boot=True, lock_timeout=5.0)
    return {"ok": True, "result": result}


@router.post("/run")
async def run_once(body: dict | None = None):
    """Trigger a single session immediately (independent of the heartbeat schedule).

    An optional {"focus": "..."} seeds an ad-hoc directive — a brief directive session driven
    from the UI.
    """
    from littleman.agent.session import run_session

    manual_context: dict = {"primary_trigger": "manual_run"}
    if body and body.get("focus"):
        manual_context["focus"] = body["focus"]
    result = await run_session(lock_timeout=5.0, manual_context=manual_context)
    return {"ok": True, "result": result}


@router.post("/run-due")
async def run_due():
    """Fire any heartbeats that are currently due (manual scheduler tick — always allowed)."""
    from littleman.heartbeat.scheduler import _tick

    fired = await _tick(force=True)
    return {"ok": True, "fired": fired}
