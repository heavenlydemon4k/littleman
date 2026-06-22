from dataclasses import dataclass, field
from decimal import Decimal

from littleman.config import settings


@dataclass
class RiskState:
    wallet_balance_usdc: Decimal
    available_balance_usdc: Decimal
    open_exposure_usdc: Decimal
    session_start_balance: Decimal
    peak_balance: Decimal
    exposure_by_category: dict[str, Decimal] = field(default_factory=dict)
    circuit_breaker_active: bool = False


@dataclass
class RiskResult:
    allowed: bool
    reason: str | None = None

    @classmethod
    def allow(cls) -> "RiskResult":
        return cls(allowed=True)

    @classmethod
    def veto(cls, reason: str) -> "RiskResult":
        return cls(allowed=False, reason=reason)


class RiskGovernor:
    def __init__(
        self,
        max_position_pct: float | None = None,
        max_exposure_pct: float | None = None,
        max_session_drawdown_pct: float | None = None,
        max_total_drawdown_pct: float | None = None,
        max_category_exposure_pct: float | None = None,
    ):
        self.max_position_pct = Decimal(str(max_position_pct or settings.max_position_pct))
        self.max_exposure_pct = Decimal(str(max_exposure_pct or settings.max_exposure_pct))
        self.max_session_drawdown_pct = Decimal(str(max_session_drawdown_pct or settings.max_session_drawdown_pct))
        self.max_total_drawdown_pct = Decimal(str(max_total_drawdown_pct or settings.max_total_drawdown_pct))
        self.max_category_exposure_pct = Decimal(str(max_category_exposure_pct or settings.max_category_exposure_pct))

    def check_bet(
        self,
        size_usdc: Decimal | float,
        state: RiskState,
        market_category: str | None = None,
    ) -> RiskResult:
        size = Decimal(str(size_usdc))

        if state.circuit_breaker_active:
            return RiskResult.veto("circuit breaker active — no new bets until user resets")

        result = self.check_circuit_breaker(state)
        if not result.allowed:
            return result

        if state.wallet_balance_usdc <= 0:
            return RiskResult.veto("wallet balance is zero or negative")

        max_position = state.wallet_balance_usdc * self.max_position_pct
        if size > max_position:
            return RiskResult.veto(
                f"position size ${size:.2f} exceeds max_position_pct limit "
                f"(${max_position:.2f} = {float(self.max_position_pct)*100:.0f}% of ${state.wallet_balance_usdc:.2f})"
            )

        new_exposure = state.open_exposure_usdc + size
        max_exposure = state.wallet_balance_usdc * self.max_exposure_pct
        if new_exposure > max_exposure:
            return RiskResult.veto(
                f"total exposure after bet ${new_exposure:.2f} would exceed max_exposure_pct limit "
                f"(${max_exposure:.2f} = {float(self.max_exposure_pct)*100:.0f}% of ${state.wallet_balance_usdc:.2f})"
            )

        if size > state.available_balance_usdc:
            return RiskResult.veto(
                f"bet size ${size:.2f} exceeds available balance ${state.available_balance_usdc:.2f}"
            )

        session_loss = state.session_start_balance - state.wallet_balance_usdc
        max_session_loss = state.session_start_balance * self.max_session_drawdown_pct
        if session_loss >= max_session_loss:
            return RiskResult.veto(
                f"session drawdown ${session_loss:.2f} has reached limit "
                f"(${max_session_loss:.2f} = {float(self.max_session_drawdown_pct)*100:.0f}% of session start)"
            )

        if market_category and state.exposure_by_category:
            category_exposure = state.exposure_by_category.get(market_category, Decimal(0))
            new_category_exposure = category_exposure + size
            max_category = state.wallet_balance_usdc * self.max_category_exposure_pct
            if new_category_exposure > max_category:
                return RiskResult.veto(
                    f"category '{market_category}' exposure ${new_category_exposure:.2f} would exceed "
                    f"max_category_exposure_pct limit (${max_category:.2f})"
                )

        return RiskResult.allow()

    def check_circuit_breaker(self, state: RiskState) -> RiskResult:
        if state.peak_balance <= 0:
            return RiskResult.allow()

        drawdown = state.peak_balance - state.wallet_balance_usdc
        max_drawdown = state.peak_balance * self.max_total_drawdown_pct

        if drawdown >= max_drawdown:
            return RiskResult.veto(
                f"total drawdown ${drawdown:.2f} from peak ${state.peak_balance:.2f} exceeds "
                f"max_total_drawdown_pct limit ({float(self.max_total_drawdown_pct)*100:.0f}%). "
                "Circuit breaker active. No new bets until user resets."
            )
        return RiskResult.allow()

    def size_by_kelly(
        self,
        estimated_probability: float,
        market_price: float,
        state: RiskState,
        kelly_fraction: float | None = None,
    ) -> Decimal:
        fraction = kelly_fraction or settings.kelly_fraction
        if market_price <= 0 or market_price >= 1:
            return Decimal(0)

        edge = estimated_probability - market_price
        if edge <= 0:
            return Decimal(0)

        odds = (1 - market_price) / market_price
        full_kelly = edge / odds
        fractional_kelly = full_kelly * fraction

        raw_size = state.wallet_balance_usdc * Decimal(str(fractional_kelly))
        max_size = state.wallet_balance_usdc * self.max_position_pct
        return min(raw_size, max_size).quantize(Decimal("0.01"))


# Module-level default instance
governor = RiskGovernor()
