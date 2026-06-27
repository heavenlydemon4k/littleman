"""Tests for construct maintenance gating."""

from __future__ import annotations

import pytest

from littleman.meta import maintain


@pytest.mark.asyncio
async def test_maintainers_are_gated_on_relevant_signals(monkeypatch):
    """Hypotheses, blockers, and skill_notes maintainers should only run when there is signal."""
    calls = set()

    def _make_flag(name: str):
        async def _flag(*_args, **_kwargs) -> bool:
            calls.add(name)
            return True

        return _flag

    monkeypatch.setattr(maintain, "_maintain_hypotheses", _make_flag("hypotheses"))
    monkeypatch.setattr(maintain, "_maintain_blockers", _make_flag("blockers"))
    monkeypatch.setattr(maintain, "_maintain_skill_notes", _make_flag("skill_notes"))
    monkeypatch.setattr(maintain, "_maintain_priorities", lambda *_a, **_k: False)
    monkeypatch.setattr(maintain, "_maintain_calendar", lambda *_a, **_k: False)
    monkeypatch.setattr(maintain, "_maintain_self", lambda *_a, **_k: False)
    monkeypatch.setattr(maintain, "_maintain_turns", lambda *_a, **_k: False)
    monkeypatch.setattr(maintain, "_maintain_calibration", lambda *_a, **_k: False)
    monkeypatch.setattr(maintain, "_render_exposure", lambda *_a, **_k: False)
    monkeypatch.setattr(maintain.runtime, "active", lambda: {"mode": "real"})
    monkeypatch.setattr(
        maintain.construct,
        "load",
        lambda: maintain.construct.Construct(
            priorities="",
            macro_plan="",
            self_model="",
            exposure="",
            calendar="",
            directive="",
            turns="",
            hypotheses="",
            blockers="",
            skill_notes="",
            reflection="",
        ),
    )

    # No signal — none of the gated maintainers run.
    result = await maintain.maintain_construct(
        directive={"intent": "test"},
        session_summary="nothing happened",
        exec_result={},
        world_state={},
        db=None,
    )
    assert not result["docs"].get("hypotheses")
    assert not result["docs"].get("blockers")
    assert not result["docs"].get("skill_notes")
    assert calls == set()

    # With signal — each gated maintainer runs.
    await maintain.maintain_construct(
        directive={"intent": "test"},
        session_summary="nothing happened",
        exec_result={
            "pending_resolutions": ["m1"],
            "failures": [{"task": "t", "error": "e"}],
            "skills_used": ["web_search"],
        },
        world_state={},
        db=None,
    )
    assert "hypotheses" in calls
    assert "blockers" in calls
    assert "skill_notes" in calls


@pytest.mark.asyncio
async def test_maintain_self_runs_with_skills_used(monkeypatch):
    """SELF.md maintainer should run when skills were used, not only when bets were placed."""
    called = []

    async def _fake_complete(*_a, **_k):
        called.append(True)
        return "NO_UPDATE"

    monkeypatch.setattr(maintain, "complete_text", _fake_complete)

    c = maintain.construct.Construct(
        priorities="",
        macro_plan="",
        self_model="",
        exposure="",
        calendar="",
        directive="",
        turns="",
        hypotheses="",
        blockers="",
        skill_notes="",
        reflection="",
    )
    result = await maintain._maintain_self(
        c,
        directive={"intent": "test"},
        summary="used a skill",
        exec_result={"skills_used": ["web_search"], "failures": []},
    )
    assert called
    assert result is False  # NO_UPDATE means no write
