"""Tests for calibration tracking and SELF.md integration."""

from __future__ import annotations

import pytest

from littleman.meta.calibration import (
    compute_calibration,
    record_outcome,
    render_calibration_markdown,
)
from littleman.meta import construct


@pytest.mark.asyncio
async def test_record_outcome(db):
    entry = await record_outcome(
        db,
        session_id="s1",
        predicted_probability=0.7,
        actual_outcome=1.0,
        domain="test",
        category="politics",
    )
    assert entry.domain == "test"
    assert float(entry.predicted_probability) == pytest.approx(0.7)
    assert float(entry.actual_outcome) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_compute_calibration_insufficient_data(db):
    stats = await compute_calibration(db, domain="test", min_samples=5)
    assert stats["insufficient_data"] is True


@pytest.mark.asyncio
async def test_compute_calibration_stats(db):
    for p, o in [(0.7, 1.0), (0.7, 0.0), (0.8, 1.0), (0.8, 1.0), (0.3, 0.0)]:
        await record_outcome(db, "s", p, o, domain="test")

    stats = await compute_calibration(db, domain="test", min_samples=5)
    assert stats["insufficient_data"] is False
    assert stats["n"] == 5
    assert "mean_brier" in stats
    assert len(stats["buckets"]) > 0


@pytest.mark.asyncio
async def test_render_calibration_markdown(db):
    for p, o in [(0.7, 1.0), (0.7, 0.0), (0.8, 1.0), (0.8, 1.0), (0.3, 0.0)]:
        await record_outcome(db, "s", p, o, domain="test")

    stats = await compute_calibration(db, domain="test", min_samples=5)
    md = render_calibration_markdown(stats)
    assert "Calibration" in md
    assert "Brier" in md
    assert "70-80%" in md


def test_replace_section_appends_when_missing():
    from littleman.meta.maintain import _replace_section

    new = _replace_section("# SELF\n\nIntro.", "Calibration", "## Calibration\n\nNo data yet.")
    assert "## Calibration" in new
    assert "No data yet" in new


def test_replace_section_replaces_existing():
    from littleman.meta.maintain import _replace_section

    original = "# SELF\n\n## Calibration\n\nOld data.\n\n## Focus\n\nStay sharp."
    new = _replace_section(original, "Calibration", "## Calibration\n\nNew data.")
    assert "New data" in new
    assert "Old data" not in new
    assert "Stay sharp" in new
