"""Self-scheduler — end-of-session heartbeat planning.

After the session's work is done, this decides what future sessions are needed and writes
heartbeat records. It is the mechanism that makes the agent's schedule self-propagating.

Deterministic cascade rules (resolution checks, research windows, idle fallback) are applied
in code; the LLM is used to decide amendments/cancellations and to fill intent-carrying
context, but the core scheduling decisions do not require a model call.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from littleman.config import settings
from littleman.heartbeat import store
from littleman.llm.complete import complete_json
from littleman.llm.prompts import HEARTBEAT_PLAN_SYSTEM, HEARTBEAT_PLAN_USER, render
from littleman.meta.world_model import WorldModelState

_CATEGORY_LEAD = {"politics": 2.0, "sports": 0.5, "crypto": 0.25}
_DEFAULT_LEAD_HOURS = 1.0
_GRACE_MINUTES = 10


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _category_of(market: dict[str, Any]) -> str:
    cat = (market.get("category") or "").lower()
    return cat if cat in _CATEGORY_LEAD else "default"


def _deterministic_plan(state: WorldModelState, now: datetime) -> list[dict[str, Any]]:
    """Apply the cascade rules to produce heartbeat specs without an LLM call."""
    specs: list[dict[str, Any]] = []

    for p in state.pending_resolutions + state.open_positions:
        specs.append(
            {
                "fire_at": (now + timedelta(minutes=_GRACE_MINUTES)).isoformat()
                if p.resolved_at is None
                else p.resolved_at,
                "reason": f"Resolution check for position {p.position_id} ({p.market_title})",
                "session_type": "RESOLVE",
                "context": {
                    "primary_trigger": "position_resolution",
                    "positions_to_check": [p.position_id],
                    "markets_to_check": [p.market_id],
                },
            }
        )

    for m in state.watched_markets:
        closes_at = m.get("closes_at")
        if not closes_at:
            continue
        try:
            close_dt = _parse_dt(closes_at)
        except (ValueError, AttributeError):
            continue
        lead = _CATEGORY_LEAD.get(_category_of(m), _DEFAULT_LEAD_HOURS)
        fire = close_dt - timedelta(hours=lead)
        if fire <= now:
            continue
        specs.append(
            {
                "fire_at": fire.isoformat(),
                "reason": f"Pre-close research window for {m.get('title', m.get('market_id'))}",
                "session_type": "RESEARCH",
                "context": {
                    "primary_trigger": "market_close_approaching",
                    "market_id": m.get("market_id"),
                    "closes_at": closes_at,
                },
            }
        )

    if not specs:
        specs.append(
            {
                "fire_at": (now + timedelta(hours=settings.idle_heartbeat_interval_hours)).isoformat(),
                "reason": "Idle maintenance scan — no specific positions or watches",
                "session_type": "FULL_CYCLE",
                "context": {"primary_trigger": "idle_maintenance"},
            }
        )

    return specs


def _dedupe_key(context: dict[str, Any], session_type: str) -> str:
    """A stable key identifying a heartbeat's trigger, for deduplication."""
    trigger = context.get("primary_trigger", session_type)
    if trigger == "position_resolution":
        ids = context.get("positions_to_check") or []
        return f"resolve:{','.join(sorted(ids))}"
    if trigger == "market_close_approaching":
        return f"research:{context.get('market_id')}"
    if trigger == "idle_maintenance":
        return "idle"
    return f"{trigger}:{session_type}"


async def plan_and_schedule(
    db: AsyncSession,
    state: WorldModelState,
    session_summary: str,
    spawned_by: str | None,
    use_llm_refinement: bool = True,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    specs = _deterministic_plan(state, now)

    # Dedupe against already-scheduled heartbeats so the cascade does not pile up duplicate
    # idle / resolution / research wakes for the same trigger.
    existing = await store.list_scheduled(db)
    existing_keys = {_dedupe_key(h.context or {}, h.session_type) for h in existing}
    specs = [s for s in specs if _dedupe_key(s["context"], s["session_type"]) not in existing_keys]

    cancel: list[dict[str, Any]] = []
    amend: list[dict[str, Any]] = []

    # Optional LLM pass to amend/cancel stale scheduled heartbeats and enrich context.
    if use_llm_refinement and state.next_heartbeats:
        try:
            scheduled = [h.model_dump() for h in state.next_heartbeats]
            system = render(
                HEARTBEAT_PLAN_SYSTEM,
                idle_hours=settings.idle_heartbeat_interval_hours,
                now=now.isoformat(),
            )
            user = render(
                HEARTBEAT_PLAN_USER,
                session_summary=session_summary,
                positions_json=json.dumps([p.model_dump() for p in state.open_positions]),
                watched_markets_json=json.dumps(state.watched_markets),
                scheduled_heartbeats_json=json.dumps(scheduled),
            )
            refined = await complete_json(system, user, tier="secondary")
            # Trust the LLM only for amend/cancel; creation stays deterministic.
            cancel = refined.get("cancel", [])
            amend = refined.get("amend", [])
        except Exception:
            # Refinement is best-effort; the deterministic plan stands on its own.
            cancel, amend = [], []

    created = []
    for spec in specs:
        hb = await store.create_heartbeat(
            db,
            fire_at=_parse_dt(spec["fire_at"]),
            reason=spec["reason"],
            session_type=spec["session_type"],
            context=spec["context"],
            spawned_by=spawned_by,
        )
        created.append(store.serialise(hb))

    for c in cancel:
        await store.cancel_heartbeat(db, c["heartbeat_id"])
    for a in amend:
        await store.amend_heartbeat(
            db,
            a["heartbeat_id"],
            fire_at=_parse_dt(a["fire_at"]) if a.get("fire_at") else None,
            reason=a.get("reason"),
            context=a.get("context"),
        )

    return {"created": created, "cancelled": cancel, "amended": amend}
