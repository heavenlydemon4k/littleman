"""Risk governor tests — the deterministic protection against losing money to a bug.

These cover every limit type and the boundary conditions. No LLM, no database — pure logic.
"""

from decimal import Decimal

import pytest

from littleman.macro.risk import RiskGovernor, RiskState


def _state(
    balance="1000",
    available="1000",
    exposure="0",
    session_start="1000",
    peak="1000",
    categories=None,
    breaker=False,
):
    return RiskState(
        wallet_balance_usdc=Decimal(balance),
        available_balance_usdc=Decimal(available),
        open_exposure_usdc=Decimal(exposure),
        session_start_balance=Decimal(session_start),
        peak_balance=Decimal(peak),
        exposure_by_category=categories or {},
        circuit_breaker_active=breaker,
    )


def _gov():
    return RiskGovernor(
        max_position_pct=0.20,
        max_exposure_pct=0.80,
        max_session_drawdown_pct=0.15,
        max_total_drawdown_pct=0.40,
        max_category_exposure_pct=0.40,
    )


def test_allow_bet_within_all_limits():
    result = _gov().check_bet(Decimal("150"), _state())
    assert result.allowed is True


def test_veto_position_over_max_pct():
    result = _gov().check_bet(Decimal("250"), _state())
    assert result.allowed is False
    assert "max_position_pct" in result.reason


def test_position_exactly_at_max_pct_is_allowed():
    # 20% of 1000 = 200 exactly — not over the limit.
    result = _gov().check_bet(Decimal("200"), _state())
    assert result.allowed is True


def test_veto_total_exposure_over_limit():
    # Existing exposure 700 + 150 = 850 > 800 (80% of 1000).
    result = _gov().check_bet(Decimal("150"), _state(exposure="700"))
    assert result.allowed is False
    assert "exposure" in result.reason


def test_veto_when_size_exceeds_available_balance():
    result = _gov().check_bet(Decimal("150"), _state(available="100"))
    assert result.allowed is False
    assert "available balance" in result.reason


def test_veto_on_session_drawdown():
    # Session started at 1000, now 840 → lost 160 ≥ 15% (150).
    result = _gov().check_bet(Decimal("10"), _state(balance="840", available="840"))
    assert result.allowed is False
    assert "session drawdown" in result.reason


def test_circuit_breaker_on_total_drawdown():
    # Peak 1000, now 550 → 450 drawdown ≥ 40% (400).
    result = _gov().check_bet(Decimal("10"), _state(balance="550", available="550", peak="1000"))
    assert result.allowed is False
    assert "circuit breaker" in result.reason.lower()


def test_explicit_circuit_breaker_flag_vetoes():
    result = _gov().check_bet(Decimal("10"), _state(breaker=True))
    assert result.allowed is False


def test_veto_category_concentration():
    # politics already 350, +100 = 450 > 40% (400).
    result = _gov().check_bet(
        Decimal("100"),
        _state(categories={"politics": Decimal("350")}),
        market_category="politics",
    )
    assert result.allowed is False
    assert "politics" in result.reason


def test_zero_balance_is_vetoed():
    result = _gov().check_bet(Decimal("10"), _state(balance="0", available="0"))
    assert result.allowed is False


def test_kelly_sizing_positive_edge():
    gov = _gov()
    size = gov.size_by_kelly(0.60, 0.50, _state())
    assert size > 0
    # Never exceeds the max position limit.
    assert size <= Decimal("200")


def test_kelly_zero_on_no_edge():
    gov = _gov()
    assert gov.size_by_kelly(0.50, 0.50, _state()) == Decimal(0)
    assert gov.size_by_kelly(0.40, 0.50, _state()) == Decimal(0)


def test_kelly_capped_at_max_position():
    gov = _gov()
    # Huge edge would suggest a large bet; cap holds at 20%.
    size = gov.size_by_kelly(0.99, 0.50, _state())
    assert size <= Decimal("200")
