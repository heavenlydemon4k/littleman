"""World model round-trip tests — the agent's persistent state must survive save/load."""

import pytest

from littleman.meta.world_model import WorldModelManager


@pytest.mark.asyncio
async def test_default_state_uses_budget(db):
    wm = WorldModelManager(db)
    state = await wm.load()
    # With no row and no positions, the wallet defaults to the configured budget.
    assert state.wallet_balance_usdc == state.available_balance_usdc
    assert state.wallet_balance_usdc > 0


@pytest.mark.asyncio
async def test_save_and_reload_roundtrip(db):
    wm = WorldModelManager(db)
    state = await wm.load()
    state.wallet_balance_usdc = 742.50
    state.available_balance_usdc = 600.00
    state.total_pnl = 42.50
    state.last_session_summary = "did a thing"
    state.watched_markets = [{"market_id": "m1", "title": "Test market"}]
    await wm.save(state)

    reloaded = await wm.load()
    assert reloaded.wallet_balance_usdc == 742.50
    assert reloaded.available_balance_usdc == 600.00
    assert reloaded.total_pnl == 42.50
    assert reloaded.last_session_summary == "did a thing"
    assert reloaded.watched_markets[0]["market_id"] == "m1"


@pytest.mark.asyncio
async def test_update_helper_persists_single_field(db):
    wm = WorldModelManager(db)
    await wm.load()
    updated = await wm.update(available_balance_usdc=123.45)
    assert updated.available_balance_usdc == 123.45
    assert (await wm.load()).available_balance_usdc == 123.45


@pytest.mark.asyncio
async def test_peak_balance_never_decreases(db):
    wm = WorldModelManager(db)
    state = await wm.load()
    start_peak = state.peak_balance
    state.wallet_balance_usdc = start_peak - 100
    await wm.save(state)
    reloaded = await wm.load()
    # Peak is the max of stored peak and current balance — a dip does not lower it.
    assert reloaded.peak_balance >= start_peak
