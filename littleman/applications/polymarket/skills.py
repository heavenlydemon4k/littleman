"""Polymarket client skills.

Read operations hit the public Gamma/CLOB APIs. Write operations (place_bet, cancel) are
gated behind the risk governor at the executor level, never called directly from here without
that gate. Live order signing requires the wallet private key and the py-clob-client library;
until those are wired, place_bet records the *intent* and returns a NOT_EXECUTED status so the
rest of the pipeline (sizing, risk, logging) can be exercised safely.
"""

from __future__ import annotations

from typing import Any

import httpx

from littleman.config import settings

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
_TIMEOUT = 20.0


async def _get(base: str, path: str, params: dict | None = None) -> Any:
    async with httpx.AsyncClient(headers={"User-Agent": "littleman/0.1"}) as client:
        resp = await client.get(f"{base}{path}", params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()


def make_polymarket_skills() -> list[dict]:
    async def scan_markets(
        category: str | None = None,
        min_volume: float | None = None,
        closes_within_hours: float | None = None,
        max_results: int = 20,
    ) -> dict:
        params: dict[str, Any] = {"closed": "false", "limit": max_results, "order": "volume", "ascending": "false"}
        if category:
            params["tag"] = category
        try:
            data = await _get(GAMMA_BASE, "/markets", params)
        except httpx.HTTPError as e:
            return {"error": str(e), "markets": []}

        markets = []
        for m in data if isinstance(data, list) else data.get("data", []):
            vol = float(m.get("volume", 0) or 0)
            if min_volume and vol < min_volume:
                continue
            markets.append(
                {
                    "market_id": m.get("id") or m.get("conditionId"),
                    "title": m.get("question"),
                    "volume": vol,
                    "closes_at": m.get("endDate"),
                    "outcomes": m.get("outcomes"),
                    "yes_price": _yes_price(m),
                }
            )
        return {"markets": markets[:max_results], "count": len(markets[:max_results])}

    async def get_market(market_id: str) -> dict:
        try:
            data = await _get(GAMMA_BASE, f"/markets/{market_id}")
        except httpx.HTTPError as e:
            return {"error": str(e)}
        return {
            "market_id": market_id,
            "title": data.get("question"),
            "description": data.get("description"),
            "resolution_criteria": data.get("description"),
            "closes_at": data.get("endDate"),
            "volume": float(data.get("volume", 0) or 0),
            "yes_price": _yes_price(data),
            "outcomes": data.get("outcomes"),
        }

    async def get_orderbook(market_id: str) -> dict:
        try:
            data = await _get(CLOB_BASE, "/book", {"token_id": market_id})
        except httpx.HTTPError as e:
            return {"error": str(e)}
        return {"market_id": market_id, "bids": data.get("bids", []), "asks": data.get("asks", [])}

    async def check_resolution(market_id: str) -> dict:
        try:
            data = await _get(GAMMA_BASE, f"/markets/{market_id}")
        except httpx.HTTPError as e:
            return {"error": str(e)}
        closed = data.get("closed", False)
        return {
            "market_id": market_id,
            "resolved": bool(closed),
            "outcome": data.get("outcome") if closed else None,
            "resolved_price": _yes_price(data) if closed else None,
        }

    return [
        {
            "name": "scan_markets",
            "fn": scan_markets,
            "description": "List open Polymarket markets matching optional filters, highest volume first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "min_volume": {"type": "number"},
                    "closes_within_hours": {"type": "number"},
                    "max_results": {"type": "integer", "default": 20},
                },
                "required": [],
            },
            "cost": "MEDIUM",
        },
        {
            "name": "get_market",
            "fn": get_market,
            "description": "Get full detail on a market including resolution criteria and price.",
            "parameters": {
                "type": "object",
                "properties": {"market_id": {"type": "string"}},
                "required": ["market_id"],
            },
            "cost": "LOW",
        },
        {
            "name": "get_orderbook",
            "fn": get_orderbook,
            "description": "Get current order book depth for a market token.",
            "parameters": {
                "type": "object",
                "properties": {"market_id": {"type": "string"}},
                "required": ["market_id"],
            },
            "cost": "LOW",
        },
        {
            "name": "check_resolution",
            "fn": check_resolution,
            "description": "Check whether a market has resolved and retrieve the outcome.",
            "parameters": {
                "type": "object",
                "properties": {"market_id": {"type": "string"}},
                "required": ["market_id"],
            },
            "cost": "LOW",
        },
    ]


def _yes_price(market: dict) -> float | None:
    prices = market.get("outcomePrices") or market.get("prices")
    if isinstance(prices, list) and prices:
        try:
            return float(prices[0])
        except (TypeError, ValueError):
            return None
    return None
