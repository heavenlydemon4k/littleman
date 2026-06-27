"""Calibration skills — record resolved outcomes and query calibration stats."""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from littleman.meta.calibration import compute_calibration, record_outcome, render_calibration_markdown


def make_calibration_skills(
    db_session_factory: Callable[[], AsyncSession],
) -> list[dict[str, Any]]:
    async def record_prediction_outcome(
        predicted_probability: float,
        actual_outcome: float,
        domain: str = "default",
        category: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record the actual outcome of a probabilistic prediction for calibration tracking."""
        async with db_session_factory() as db:
            entry = await record_outcome(
                db,
                session_id="chat",  # overwritten by applications that know the real session id
                predicted_probability=predicted_probability,
                actual_outcome=actual_outcome,
                domain=domain,
                category=category,
                context=context,
            )
            return {
                "recorded": True,
                "id": entry.id,
                "domain": entry.domain,
                "predicted_probability": float(entry.predicted_probability),
                "actual_outcome": float(entry.actual_outcome),
            }

    async def get_calibration_summary(domain: str = "default") -> dict[str, Any]:
        """Return calibration statistics for a domain."""
        async with db_session_factory() as db:
            stats = await compute_calibration(db, domain=domain)
            stats["markdown"] = render_calibration_markdown(stats)
            return stats

    return [
        {
            "name": "record_prediction_outcome",
            "fn": record_prediction_outcome,
            "description": (
                "Record the actual outcome (0.0 or 1.0) of a past probabilistic prediction "
                "so the agent can track its calibration over time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "predicted_probability": {
                        "type": "number",
                        "description": "The probability the agent predicted (0.0 to 1.0).",
                    },
                    "actual_outcome": {
                        "type": "number",
                        "description": "The actual outcome: 0.0 or 1.0.",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Domain or application this prediction belongs to.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional sub-category for domain-specific grouping.",
                    },
                    "context": {
                        "type": "object",
                        "description": "Optional context (market_id, question, etc.).",
                    },
                },
                "required": ["predicted_probability", "actual_outcome"],
            },
            "cost": "LOW",
        },
        {
            "name": "get_calibration_summary",
            "fn": get_calibration_summary,
            "description": (
                "Return calibration statistics (Brier score, accuracy by confidence bucket) "
                "for a domain. Use this to assess whether the agent is over- or under-confident."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain to summarize (default: 'default').",
                    },
                },
                "required": [],
            },
            "cost": "LOW",
        },
    ]
