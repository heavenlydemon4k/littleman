"""EXPOSURE.md — deterministic risk-map renderer + fake-mode maintenance.

EXPOSURE.md is drawn from the world model with no LLM, so it must render correctly from a
snapshot dict and be written even in fake mode (where the agent-authored docs are skipped).
"""

import pytest

from littleman.config import settings
from littleman.meta import construct
from littleman.meta.exposure import render_exposure


FULL = {
    "wallet_balance_usdc": 420.0,
    "available_balance_usdc": 300.0,
    "total_pnl": -80.0,
    "open_exposure_usdc": 120.0,
    "exposure_by_category": {"politics": 90.0, "crypto": 30.0},
    "peak_balance": 500.0,
    "circuit_breaker_active": True,
    "open_positions": [
        {"market_title": "Trump 2024", "market_id": "politics-trump", "direction": "YES",
         "size_usdc": 90.0, "entry_price": 0.62, "pnl": -10.0},
        {"market_title": "BTC > 100k", "market_id": "crypto-btc", "direction": "NO",
         "size_usdc": 30.0, "entry_price": 0.40, "pnl": None},
    ],
    "pending_resolutions": [],
}


def test_render_includes_capital_and_exposure():
    md = render_exposure(FULL)
    assert "$420.00" in md            # balance
    assert "$120.00" in md            # exposure
    assert "politics" in md and "$90.00" in md
    assert "Trump 2024" in md


def test_render_drawdown_from_peak():
    md = render_exposure(FULL)
    # peak 500 - balance 420 = 80 drawdown, 16.0% from peak
    assert "$80.00" in md
    assert "16.0% from peak" in md


def test_render_circuit_breaker_flagged():
    assert "ACTIVE" in render_exposure(FULL)
    assert "inactive" in render_exposure({**FULL, "circuit_breaker_active": False})


def test_render_tolerates_empty_snapshot():
    md = render_exposure({})
    assert "EXPOSURE.md" in md
    assert "$0.00" in md  # zero balance, no crash


def test_render_sums_exposure_when_total_absent():
    ws = {k: v for k, v in FULL.items() if k != "open_exposure_usdc"}
    md = render_exposure(ws)
    assert "$120.00" in md  # 90 + 30 summed from positions


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    ws = tmp_path / "workspace"
    (ws / "construct").mkdir(parents=True)
    for name in construct.ALL_DOCS:
        stem = name.replace(".md", "")
        (ws / "construct" / f"{stem}.template.md").write_text(f"<!-- {name} -->\n", encoding="utf-8")
    monkeypatch.setattr(settings, "workspace_dir", ws)
    return ws


@pytest.mark.asyncio
async def test_maintain_renders_exposure_in_fake_mode(temp_workspace, monkeypatch):
    from littleman.llm import runtime
    from littleman.meta.maintain import maintain_construct

    monkeypatch.setattr(runtime, "active", lambda: {"mode": "fake"})
    construct.seed_from_templates()

    result = await maintain_construct({}, "did a thing", {}, world_state=FULL)

    assert result["docs"]["exposure"] is True
    loaded = construct.load()
    assert "$420.00" in loaded.exposure
    assert "Trump 2024" in loaded.exposure


def test_exposure_is_not_agent_writable():
    # EXPOSURE.md is rendered, never agent-authored: not in the OVERWRITE (writable) set.
    assert "EXPOSURE.md" not in construct.OVERWRITE_DOCS
    assert "EXPOSURE.md" in construct.RENDERED_DOCS
    assert "EXPOSURE.md" in construct.ALL_DOCS
