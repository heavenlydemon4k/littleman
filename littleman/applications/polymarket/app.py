"""Polymarket application plug-in.

Encapsulates all Polymarket-specific behaviour: skill registration, read-only reconciliation,
EXECUTE-task handling (bet sizing + risk-gated intent recording), and dashboard status.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from littleman.applications import Application, register_builtin
from littleman.config import settings
from littleman.db.models import Observation, Position
from littleman.macro.risk import RiskGovernor, RiskState
from littleman.meta.world_model import WorldModelManager, WorldModelState


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _risk_state(state: WorldModelState) -> RiskState:
    from decimal import Decimal

    return RiskState(
        wallet_balance_usdc=Decimal(str(state.wallet_balance_usdc)),
        available_balance_usdc=Decimal(str(state.available_balance_usdc)),
        open_exposure_usdc=Decimal(str(state.open_exposure_usdc())),
        session_start_balance=Decimal(str(state.session_start_balance)),
        peak_balance=Decimal(str(state.peak_balance)),
        exposure_by_category={k: Decimal(str(v)) for k, v in state.exposure_by_category().items()},
        circuit_breaker_active=state.circuit_breaker_active,
    )


class PolymarketApplication(Application):
    name = "Polymarket trading"

    def is_configured(self) -> bool:
        return bool(settings.polymarket_wallet_address)

    def register_skills(
        self,
        registry: Any,
        db_session_factory: Any | None = None,
    ) -> None:
        from littleman.applications.polymarket.client import make_account_skills
        from littleman.applications.polymarket.skills import make_polymarket_skills

        for skill in make_polymarket_skills():
            registry.register(**skill)
        for skill in make_account_skills():
            registry.register(**skill)

    async def reconcile(self, db: Any) -> dict[str, Any]:
        from littleman.applications.polymarket.client import reconcile

        return await reconcile(db)

    async def execute(self, ctx: Any, node: Any) -> dict[str, Any]:
        """Handle an EXECUTE task: size and record a Polymarket bet, gated by the risk governor."""
        p = node.params
        market_id = p.get("market_id")
        direction = (p.get("direction") or "").upper()
        market_price = _to_float(p.get("market_price"))
        estimated_probability = _to_float(p.get("estimated_probability"))
        category = p.get("category")

        if not market_id or direction not in ("YES", "NO"):
            return {"status": "NO_BET", "reason": "missing market_id or valid direction"}
        if market_price is None or estimated_probability is None:
            return {
                "status": "NO_BET",
                "reason": "missing market_price or estimated_probability — research first, then bet",
            }

        state = await ctx.wm.load()
        risk_state = _risk_state(state)

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

        position = Position(
            id=str(uuid.uuid4()),
            market_id=market_id,
            market_title=p.get("market_title", market_id),
            direction=direction,
            size_usdc=size,
            entry_price=Decimal(str(market_price)),
            predicted_probability=Decimal(str(estimated_probability)),
            status="OPEN",
            external_order_id=None,
        )
        ctx.db.add(position)

        new_available = Decimal(str(state.available_balance_usdc)) - size
        await ctx.wm.update(available_balance_usdc=float(new_available))
        await ctx.db.commit()

        return {
            "status": "PLACED",
            "position_id": position.id,
            "size_usdc": float(size),
            "note": "intent recorded; live order signing not yet wired",
        }

    def dashboard_status(self) -> dict[str, Any]:
        wallet_connected = bool(settings.polymarket_wallet_address)
        return {
            "name": "polymarket_wallet",
            "ok": wallet_connected,
            "detail": (
                f"{settings.polymarket_wallet_address} — configured"
                if wallet_connected
                else "not configured — balance is the simulated budget, no live wallet"
            ),
        }

    def root_goal(self) -> dict[str, str]:
        return {
            "title": "Maximize risk-adjusted return on Polymarket budget",
            "rationale": "Core objective: compound USDC balance through prediction market edge",
        }


register_builtin("Polymarket trading", lambda: PolymarketApplication())
