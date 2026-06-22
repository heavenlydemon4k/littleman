"""Probability estimation skill — an LLM call that produces a calibrated estimate.

This is the analytical core of a bet decision. It deliberately forms an estimate from
evidence first, then notes the market price for comparison, to avoid anchoring.
"""

from __future__ import annotations

from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from littleman.llm.complete import complete_json
from littleman.llm.prompts import PROBABILITY_SYSTEM, PROBABILITY_USER


def make_probability_skill(db_factory: Callable[[], AsyncSession]) -> list[dict]:
    async def estimate_probability(
        market_id: str,
        evidence_summary: str,
        market_title: str = "",
        resolution_criteria: str = "",
        market_price: float | None = None,
        comparable_base_rates: str | None = None,
    ) -> dict:
        user = PROBABILITY_USER.format(
            market_title=market_title or market_id,
            market_id=market_id,
            resolution_criteria=resolution_criteria or "(not provided)",
            market_price=market_price if market_price is not None else "(unknown)",
            evidence_summary=evidence_summary,
            base_rates=comparable_base_rates or "(none provided)",
        )
        estimate = await complete_json(PROBABILITY_SYSTEM, user, tier="primary")
        estimate["market_id"] = market_id
        if market_price is not None and "estimated_probability" in estimate:
            estimate["edge"] = round(estimate["estimated_probability"] - market_price, 4)
        return estimate

    return [
        {
            "name": "estimate_probability",
            "fn": estimate_probability,
            "description": (
                "Produce a calibrated probability estimate for a market from evidence. "
                "Forms its own estimate before considering the market price."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "market_id": {"type": "string"},
                    "evidence_summary": {"type": "string"},
                    "market_title": {"type": "string"},
                    "resolution_criteria": {"type": "string"},
                    "market_price": {"type": "number"},
                    "comparable_base_rates": {"type": "string"},
                },
                "required": ["market_id", "evidence_summary"],
            },
            "cost": "HIGH",
        },
    ]
