"""Polymarket account reconciliation — read-only chain + Data API access.

This reads the configured wallet's real USDC.e balance (via a Polygon RPC eth_call) and its
open positions (via the Polymarket Data API), and reconciles them into the world model. It
needs ONLY the public wallet address — no private key, no signing — so it cannot move funds.

Live order signing (which DOES need the private key) is a separate, later module; see
docs/applications/polymarket.md. The chain is the source of truth for financial state, per the
architectural meta.
"""

from __future__ import annotations

from typing import Any

import httpx

from littleman.config import settings

_TIMEOUT = 20.0
_BALANCE_OF_SELECTOR = "0x70a08231"  # keccak256("balanceOf(address)")[:4]
_USDC_DECIMALS = 6


async def get_usdc_balance(address: str) -> float:
    """Read the wallet's USDC.e balance on Polygon via a public RPC eth_call (balanceOf)."""
    data = _BALANCE_OF_SELECTOR + address.lower().replace("0x", "").rjust(64, "0")
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": settings.usdc_contract, "data": data}, "latest"],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(settings.polygon_rpc_url, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        body = resp.json()
    if "error" in body:
        raise RuntimeError(f"Polygon RPC error: {body['error']}")
    raw_hex = body.get("result", "0x0")
    return int(raw_hex, 16) / (10 ** _USDC_DECIMALS)


async def get_positions(address: str) -> list[dict[str, Any]]:
    """Read open positions for the wallet from the Polymarket Data API."""
    async with httpx.AsyncClient(headers={"User-Agent": "littleman/0.1"}) as client:
        resp = await client.get(
            f"{settings.polymarket_data_api}/positions",
            params={"user": address},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    return data if isinstance(data, list) else data.get("positions", [])


def _position_value(p: dict[str, Any]) -> float:
    for key in ("currentValue", "current_value", "value", "currentValueUsd"):
        if key in p and p[key] is not None:
            try:
                return float(p[key])
            except (TypeError, ValueError):
                continue
    # Fall back to size * current price if a discrete value field is absent.
    try:
        return float(p.get("size", 0) or 0) * float(p.get("curPrice", p.get("price", 0)) or 0)
    except (TypeError, ValueError):
        return 0.0


async def reconcile(db) -> dict[str, Any]:
    """Reconcile the wallet's real balance + positions into the world model.

    Returns a summary for the UI. Read-only: no funds can move.
    """
    from littleman.meta.world_model import WorldModelManager

    address = settings.polymarket_wallet_address
    if not address:
        return {"reconciled": False, "reason": "no POLYMARKET_WALLET_ADDRESS configured"}

    try:
        usdc = await get_usdc_balance(address)
    except (httpx.HTTPError, RuntimeError, ValueError) as e:
        return {"reconciled": False, "reason": f"balance read failed: {e}"}

    try:
        positions = await get_positions(address)
    except httpx.HTTPError:
        positions = []  # positions are best-effort; balance is the critical figure

    positions_value = round(sum(_position_value(p) for p in positions), 2)
    total = round(usdc + positions_value, 2)

    from datetime import datetime, timezone

    wm = WorldModelManager(db)
    state = await wm.load()
    state.available_balance_usdc = round(usdc, 2)
    state.wallet_balance_usdc = total
    if total > state.peak_balance:
        state.peak_balance = total
    state.wallet_reconciled = True
    state.last_reconcile_at = datetime.now(timezone.utc).isoformat()
    await wm.save(state)

    return {
        "reconciled": True,
        "address": address,
        "usdc_balance": round(usdc, 2),
        "positions_count": len(positions),
        "positions_value": positions_value,
        "total_value": total,
    }
