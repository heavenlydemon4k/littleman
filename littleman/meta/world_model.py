import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from littleman.config import settings
from littleman.db.models import Heartbeat, Position, WorldModel


class PositionSummary(BaseModel):
    position_id: str
    market_id: str
    market_title: str
    direction: str
    size_usdc: float
    entry_price: float
    predicted_probability: float
    status: str
    placed_at: str
    resolved_at: str | None = None
    pnl: float | None = None


class HeartbeatSummary(BaseModel):
    id: str
    fire_at: str
    reason: str
    session_type: str


class WorldModelState(BaseModel):
    wallet_balance_usdc: float = 0.0
    available_balance_usdc: float = 0.0
    total_pnl: float = 0.0
    open_positions: list[PositionSummary] = []
    pending_resolutions: list[PositionSummary] = []
    watched_markets: list[dict[str, Any]] = []
    active_research_topics: list[str] = []
    next_heartbeats: list[HeartbeatSummary] = []
    last_full_scan: str | None = None
    last_session_summary: str | None = None
    calibration_by_category: dict[str, Any] = {}
    session_start_balance: float = 0.0
    peak_balance: float = 0.0
    circuit_breaker_active: bool = False
    updated_at: str | None = None

    def open_exposure_usdc(self) -> float:
        return sum(p.size_usdc for p in self.open_positions)

    def exposure_by_category(self) -> dict[str, float]:
        cats: dict[str, float] = {}
        for p in self.open_positions:
            cat = (p.market_id.split("-")[0] if "-" in p.market_id else "unknown")
            cats[cat] = cats.get(cat, 0.0) + p.size_usdc
        return cats

    def stale_fields(self, stale_threshold_hours: int = 6) -> list[str]:
        stale = []
        if self.last_full_scan:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(self.last_full_scan)
            if age > timedelta(hours=stale_threshold_hours):
                stale.append(f"last_full_scan (age: {age.total_seconds()/3600:.1f}h)")
        return stale


class WorldModelManager:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def load(self) -> WorldModelState:
        result = await self.db.execute(select(WorldModel).where(WorldModel.id == 1))
        row = result.scalar_one_or_none()

        positions_result = await self.db.execute(
            select(Position).where(Position.status.in_(["OPEN", "PENDING_RESOLUTION"]))
        )
        positions = positions_result.scalars().all()

        heartbeats_result = await self.db.execute(
            select(Heartbeat)
            .where(Heartbeat.status == "SCHEDULED")
            .order_by(Heartbeat.fire_at)
            .limit(10)
        )
        heartbeats = heartbeats_result.scalars().all()

        open_positions = [
            PositionSummary(
                position_id=p.id,
                market_id=p.market_id,
                market_title=p.market_title,
                direction=p.direction,
                size_usdc=float(p.size_usdc),
                entry_price=float(p.entry_price),
                predicted_probability=float(p.predicted_probability),
                status=p.status,
                placed_at=p.placed_at.isoformat() if p.placed_at else "",
                resolved_at=p.resolved_at.isoformat() if p.resolved_at else None,
                pnl=float(p.pnl) if p.pnl else None,
            )
            for p in positions
            if p.status == "OPEN"
        ]

        pending = [
            PositionSummary(
                position_id=p.id,
                market_id=p.market_id,
                market_title=p.market_title,
                direction=p.direction,
                size_usdc=float(p.size_usdc),
                entry_price=float(p.entry_price),
                predicted_probability=float(p.predicted_probability),
                status=p.status,
                placed_at=p.placed_at.isoformat() if p.placed_at else "",
            )
            for p in positions
            if p.status == "PENDING_RESOLUTION"
        ]

        hb_summaries = [
            HeartbeatSummary(
                id=h.id,
                fire_at=h.fire_at.isoformat(),
                reason=h.reason,
                session_type=h.session_type,
            )
            for h in heartbeats
        ]

        if row is None:
            balance = settings.budget_usdc
            return WorldModelState(
                wallet_balance_usdc=balance,
                available_balance_usdc=balance,
                total_pnl=0.0,
                open_positions=open_positions,
                pending_resolutions=pending,
                next_heartbeats=hb_summaries,
                session_start_balance=balance,
                peak_balance=balance,
            )

        extended = row.extended_state or {}
        balance = float(row.wallet_balance_usdc)
        peak = max(balance, extended.get("peak_balance", balance))

        return WorldModelState(
            wallet_balance_usdc=balance,
            available_balance_usdc=float(row.available_balance_usdc),
            total_pnl=float(row.total_pnl),
            open_positions=open_positions,
            pending_resolutions=pending,
            watched_markets=extended.get("watched_markets", []),
            active_research_topics=extended.get("active_research_topics", []),
            next_heartbeats=hb_summaries,
            last_full_scan=row.last_full_scan.isoformat() if row.last_full_scan else None,
            last_session_summary=extended.get("last_session_summary"),
            calibration_by_category=extended.get("calibration_by_category", {}),
            session_start_balance=extended.get("session_start_balance", balance),
            peak_balance=peak,
            circuit_breaker_active=extended.get("circuit_breaker_active", False),
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        )

    async def save(self, state: WorldModelState) -> None:
        result = await self.db.execute(select(WorldModel).where(WorldModel.id == 1))
        row = result.scalar_one_or_none()

        extended = {
            "watched_markets": state.watched_markets,
            "active_research_topics": state.active_research_topics,
            "last_session_summary": state.last_session_summary,
            "calibration_by_category": state.calibration_by_category,
            "session_start_balance": state.session_start_balance,
            "peak_balance": state.peak_balance,
            "circuit_breaker_active": state.circuit_breaker_active,
        }

        if row is None:
            row = WorldModel(
                id=1,
                wallet_balance_usdc=Decimal(str(state.wallet_balance_usdc)),
                available_balance_usdc=Decimal(str(state.available_balance_usdc)),
                total_pnl=Decimal(str(state.total_pnl)),
                extended_state=extended,
            )
            self.db.add(row)
        else:
            row.wallet_balance_usdc = Decimal(str(state.wallet_balance_usdc))
            row.available_balance_usdc = Decimal(str(state.available_balance_usdc))
            row.total_pnl = Decimal(str(state.total_pnl))
            row.extended_state = extended

        await self.db.commit()

    async def update(self, **fields: Any) -> WorldModelState:
        state = await self.load()
        for k, v in fields.items():
            if hasattr(state, k):
                setattr(state, k, v)
        await self.save(state)
        return state
