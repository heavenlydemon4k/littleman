"""Calibration tracking — measured accuracy of the agent's probabilistic predictions.

Records resolved predictions, computes Brier scores and accuracy by confidence bucket, and
produces a markdown summary suitable for SELF.md. Domain-agnostic: applications (e.g. Polymarket)
record outcomes; the platform computes the metrics.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from littleman.db.models import CalibrationEntry


def _brier(predicted: float, actual: float) -> float:
    """Brier score: (p - o)^2; lower is better."""
    return (predicted - actual) ** 2


def _bucket(p: float) -> str:
    """Confidence bucket for calibration charts."""
    pct = int(p * 100)
    lower = (pct // 10) * 10
    upper = lower + 10
    return f"{lower}-{upper}%"


async def record_outcome(
    db: AsyncSession,
    session_id: str,
    predicted_probability: float,
    actual_outcome: float,
    domain: str = "default",
    category: str | None = None,
    context: dict[str, Any] | None = None,
    resolved_at: datetime | None = None,
) -> CalibrationEntry:
    """Record a resolved prediction for later calibration analysis."""
    entry = CalibrationEntry(
        id=str(uuid.uuid4()),
        session_id=session_id,
        domain=domain,
        category=category,
        predicted_probability=Decimal(str(predicted_probability)).quantize(Decimal("0.0001")),
        actual_outcome=Decimal(str(actual_outcome)).quantize(Decimal("0.0001")),
        context=context or {},
        resolved_at=resolved_at or datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.commit()
    return entry


async def compute_calibration(
    db: AsyncSession,
    domain: str | None = None,
    min_samples: int = 5,
) -> dict[str, Any]:
    """Compute calibration statistics for a domain (or all domains)."""
    q = select(CalibrationEntry)
    if domain:
        q = q.where(CalibrationEntry.domain == domain)
    result = await db.execute(q)
    entries = list(result.scalars().all())

    if len(entries) < min_samples:
        return {"n": len(entries), "insufficient_data": True}

    total_brier = 0.0
    by_bucket: dict[str, dict[str, Any]] = {}
    by_category: dict[str, dict[str, float]] = {}

    for e in entries:
        p = float(e.predicted_probability)
        o = float(e.actual_outcome)
        brier = _brier(p, o)
        total_brier += brier

        bucket = _bucket(p)
        if bucket not in by_bucket:
            by_bucket[bucket] = {"n": 0, "predicted_sum": 0.0, "actual_sum": 0.0}
        by_bucket[bucket]["n"] += 1
        by_bucket[bucket]["predicted_sum"] += p
        by_bucket[bucket]["actual_sum"] += o

        cat = e.category or "uncategorized"
        if cat not in by_category:
            by_category[cat] = {"n": 0, "brier_sum": 0.0}
        by_category[cat]["n"] += 1
        by_category[cat]["brier_sum"] += brier

    n = len(entries)
    mean_brier = total_brier / n

    bucket_rows = []
    for bucket, data in sorted(by_bucket.items()):
        avg_predicted = data["predicted_sum"] / data["n"]
        avg_actual = data["actual_sum"] / data["n"]
        bucket_rows.append(
            {
                "bucket": bucket,
                "n": data["n"],
                "avg_predicted": round(avg_predicted, 4),
                "avg_actual": round(avg_actual, 4),
                "gap": round(avg_predicted - avg_actual, 4),
            }
        )

    category_rows = []
    for cat, data in sorted(by_category.items()):
        category_rows.append(
            {
                "category": cat,
                "n": data["n"],
                "mean_brier": round(data["brier_sum"] / data["n"], 4),
            }
        )

    return {
        "n": n,
        "mean_brier": round(mean_brier, 4),
        "buckets": bucket_rows,
        "categories": category_rows,
        "insufficient_data": False,
    }


def render_calibration_markdown(stats: dict[str, Any]) -> str:
    """Render calibration stats as a markdown block for SELF.md."""
    if stats.get("insufficient_data"):
        return f"## Calibration\n\n{stats.get('n', 0)} resolved predictions — not enough data for reliable calibration.\n"

    lines = [
        "## Calibration",
        "",
        f"Resolved predictions: **{stats['n']}**  ",
        f"Mean Brier score: **{stats['mean_brier']}** (lower is better)",
        "",
        "### Accuracy by confidence bucket",
        "",
        "| Bucket | N | Avg predicted | Avg actual | Gap |",
        "|---|---|---|---|---|",
    ]
    for row in stats["buckets"]:
        lines.append(
            f"| {row['bucket']} | {row['n']} | {row['avg_predicted']:.0%} | "
            f"{row['avg_actual']:.0%} | {row['gap']:+.0%} |"
        )

    lines += [
        "",
        "### Accuracy by category",
        "",
        "| Category | N | Mean Brier |",
        "|---|---|---|",
    ]
    for row in stats["categories"]:
        lines.append(f"| {row['category']} | {row['n']} | {row['mean_brier']} |")

    lines.append("")
    return "\n".join(lines)


async def recent_entries(
    db: AsyncSession,
    domain: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return recent resolved predictions for inspection."""
    q = select(CalibrationEntry).order_by(CalibrationEntry.resolved_at.desc()).limit(limit)
    if domain:
        q = q.where(CalibrationEntry.domain == domain)
    result = await db.execute(q)
    return [
        {
            "id": e.id,
            "domain": e.domain,
            "category": e.category,
            "predicted_probability": float(e.predicted_probability),
            "actual_outcome": float(e.actual_outcome),
            "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        }
        for e in result.scalars().all()
    ]
