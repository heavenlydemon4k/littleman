"""Polymarket reconcile tests — read-only balance/position → world model.

The chain/Data-API calls are monkeypatched so the test is deterministic and offline; the value
math and world-model write are what we verify.
"""

import pytest

from littleman.config import settings
from littleman.skills import polymarket_client as pc


def test_position_value_prefers_explicit_field():
    assert pc._position_value({"currentValue": "12.5"}) == 12.5
    assert pc._position_value({"value": 7}) == 7.0
    # Falls back to size * price.
    assert pc._position_value({"size": 10, "curPrice": 0.4}) == 4.0
    assert pc._position_value({}) == 0.0


@pytest.mark.asyncio
async def test_reconcile_updates_world_model(db, monkeypatch):
    monkeypatch.setattr(settings, "polymarket_wallet_address", "0xabc")

    async def fake_balance(addr):
        return 123.45

    async def fake_positions(addr):
        return [{"currentValue": 10.0}, {"currentValue": 5.5}]

    monkeypatch.setattr(pc, "get_pusd_balance", fake_balance)
    monkeypatch.setattr(pc, "get_positions", fake_positions)

    result = await pc.reconcile(db)
    assert result["reconciled"] is True
    assert result["pusd_balance"] == 123.45
    assert result["positions_value"] == 15.5
    assert result["total_value"] == 138.95

    from littleman.meta.world_model import WorldModelManager

    state = await WorldModelManager(db).load()
    assert state.available_balance_usdc == 123.45
    assert state.wallet_balance_usdc == 138.95
    assert state.wallet_reconciled is True
    assert state.last_reconcile_at is not None


@pytest.mark.asyncio
async def test_reconcile_no_wallet_configured(db, monkeypatch):
    monkeypatch.setattr(settings, "polymarket_wallet_address", "")
    result = await pc.reconcile(db)
    assert result["reconciled"] is False


@pytest.mark.asyncio
async def test_reconcile_balance_failure_is_graceful(db, monkeypatch):
    monkeypatch.setattr(settings, "polymarket_wallet_address", "0xabc")

    async def boom(addr):
        raise RuntimeError("rpc down")

    monkeypatch.setattr(pc, "get_pusd_balance", boom)
    result = await pc.reconcile(db)
    assert result["reconciled"] is False
    assert "balance read failed" in result["reason"]
