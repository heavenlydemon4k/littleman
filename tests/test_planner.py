"""Self-scheduler tests — focused on the CALENDAR.md -> heartbeat bridge."""

from datetime import datetime, timedelta, timezone

import pytest

from littleman.config import settings
from littleman.heartbeat import store
from littleman.meta import construct, planner
from littleman.meta.world_model import WorldModelState


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    ws = tmp_path / "workspace"
    (ws / "construct").mkdir(parents=True)
    for name in construct.ALL_DOCS:
        stem = name.replace(".md", "")
        (ws / "construct" / f"{stem}.template.md").write_text(
            f"<!-- TEMPLATE {name} -->\n", encoding="utf-8"
        )
    monkeypatch.setattr(settings, "workspace_dir", ws)
    construct.seed_from_templates()
    return ws


def _write_calendar(*lines: str) -> None:
    construct.write_doc("CALENDAR.md", "# CALENDAR\n## Upcoming\n" + "\n".join(lines) + "\n")


def test_calendar_specs_parses_future_entries(temp_workspace):
    soon = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    _write_calendar(
        f"- {soon} | RESEARCH | refresh BTC estimate",
        "- 2000-01-01T00:00:00Z | RESOLVE | already in the past, ignore",
        "- not a real line",
        f"- {soon} | NONSENSE | bad session type, ignore",
    )
    specs = planner._calendar_specs(datetime.now(timezone.utc))
    assert len(specs) == 1
    assert specs[0]["session_type"] == "RESEARCH"
    assert specs[0]["reason"] == "refresh BTC estimate"
    assert specs[0]["context"]["primary_trigger"] == "calendar_event"


def test_calendar_specs_naive_datetime_treated_as_utc(temp_workspace):
    soon = (datetime.now(timezone.utc) + timedelta(hours=2)).replace(tzinfo=None).isoformat()
    _write_calendar(f"- {soon} | MONITOR | naive time")
    specs = planner._calendar_specs(datetime.now(timezone.utc))
    assert len(specs) == 1
    assert specs[0]["session_type"] == "MONITOR"


@pytest.mark.asyncio
async def test_plan_and_schedule_creates_heartbeat_from_calendar(temp_workspace, db):
    soon = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
    _write_calendar(f"- {soon} | RESOLVE | election market resolves")

    result = await planner.plan_and_schedule(
        db, WorldModelState(), session_summary="t", spawned_by=None, use_llm_refinement=False
    )
    assert len(result["created"]) == 1
    scheduled = await store.list_scheduled(db)
    assert any(h.context.get("primary_trigger") == "calendar_event" for h in scheduled)


@pytest.mark.asyncio
async def test_calendar_entry_suppresses_idle_fallback(temp_workspace, db):
    soon = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
    _write_calendar(f"- {soon} | RESEARCH | watch this")

    result = await planner.plan_and_schedule(
        db, WorldModelState(), session_summary="t", spawned_by=None, use_llm_refinement=False
    )
    triggers = {c["context"]["primary_trigger"] for c in result["created"]}
    assert "calendar_event" in triggers
    assert "idle_maintenance" not in triggers


@pytest.mark.asyncio
async def test_calendar_heartbeat_not_duplicated_across_wakes(temp_workspace, db):
    soon = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
    _write_calendar(f"- {soon} | RESOLVE | resolves later")

    await planner.plan_and_schedule(
        db, WorldModelState(), session_summary="t", spawned_by=None, use_llm_refinement=False
    )
    second = await planner.plan_and_schedule(
        db, WorldModelState(), session_summary="t", spawned_by=None, use_llm_refinement=False
    )
    assert second["created"] == []


@pytest.mark.asyncio
async def test_empty_calendar_falls_back_to_idle(temp_workspace, db):
    result = await planner.plan_and_schedule(
        db, WorldModelState(), session_summary="t", spawned_by=None, use_llm_refinement=False
    )
    triggers = {c["context"]["primary_trigger"] for c in result["created"]}
    assert triggers == {"idle_maintenance"}
