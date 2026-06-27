"""Tests for the OpenClaw-informed hardening: session lock, skill gating, context budget."""

import asyncio

import pytest

from littleman.agent.lock import SessionLock, SessionLockBusy
from littleman.config import settings
from littleman.meta import construct
from littleman.skills.registry import SkillRegistry


# ── Session lock ──────────────────────────────────────────────────────────────

@pytest.fixture
def temp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_dir", tmp_path / "workspace")
    return tmp_path


@pytest.mark.asyncio
async def test_lock_is_exclusive(temp_state):
    async with SessionLock(timeout=0):
        # A second acquisition with no wait must fail while the first is held.
        with pytest.raises(SessionLockBusy):
            async with SessionLock(timeout=0):
                pass


@pytest.mark.asyncio
async def test_lock_releases_on_exit(temp_state):
    async with SessionLock(timeout=0):
        pass
    # Now free — re-acquire must succeed.
    async with SessionLock(timeout=0):
        pass


@pytest.mark.asyncio
async def test_lock_waits_then_acquires(temp_state):
    held = SessionLock(timeout=0)
    await held.__aenter__()

    async def release_soon():
        await asyncio.sleep(0.2)
        await held.__aexit__(None, None, None)

    asyncio.create_task(release_soon())
    # Waiter with a timeout should succeed once the holder releases.
    async with SessionLock(timeout=2.0, poll_interval=0.05):
        pass


@pytest.mark.asyncio
async def test_stale_lock_taken_over(temp_state):
    # A lock older than max_age is considered stale and taken over.
    async with SessionLock(timeout=0):
        async with SessionLock(timeout=0, max_age=-1):  # everything is "older than" -1s
            pass


# ── Skill gating ──────────────────────────────────────────────────────────────

async def _noop(**kwargs):
    return {"ok": True}


def test_skill_unavailable_when_requirement_missing(monkeypatch):
    monkeypatch.setattr(settings, "search_api_key", "")
    reg = SkillRegistry()
    reg.register("web_search", _noop, "search", {"type": "object"}, requires=["search_api_key"])
    assert "web_search" not in reg.names()
    assert all(d["function"]["name"] != "web_search" for d in reg.get_definitions())
    assert "UNAVAILABLE" in reg.summary_text()


def test_skill_available_when_requirement_present(monkeypatch):
    monkeypatch.setattr(settings, "search_api_key", "sk-test")
    reg = SkillRegistry()
    reg.register("web_search", _noop, "search", {"type": "object"}, requires=["search_api_key"])
    assert "web_search" in reg.names()


@pytest.mark.asyncio
async def test_dispatch_blocks_unavailable_skill(monkeypatch):
    monkeypatch.setattr(settings, "search_api_key", "")
    reg = SkillRegistry()
    reg.register("web_search", _noop, "search", {"type": "object"}, requires=["search_api_key"])
    with pytest.raises(ValueError, match="unavailable"):
        await reg.dispatch("web_search", {})


def test_skill_with_no_requirements_is_available():
    reg = SkillRegistry()
    reg.register("browse_url", _noop, "fetch", {"type": "object"})
    assert "browse_url" in reg.names()


# ── Context budget ────────────────────────────────────────────────────────────

def _construct(**overrides) -> construct.Construct:
    base = dict(priorities="", macro_plan="", self_model="", exposure="", calendar="", directive="", turns="", reflection="")
    base.update(overrides)
    return construct.Construct(**base)


def test_per_doc_truncation_keeps_head():
    c = _construct(self_model="HEAD" + "x" * 5000)
    block = c.as_prompt_block(include=("SELF.md",), per_doc_max=100, total_max=10_000)
    assert "HEAD" in block
    assert "truncated" in block
    assert len(block) < 300


def test_reflection_truncates_to_tail():
    c = _construct(reflection="x" * 5000 + "RECENT_ENTRY")
    block = c.as_prompt_block(include=("REFLECTION.md",), per_doc_max=100, total_max=10_000)
    # The newest content (tail) is what survives.
    assert "RECENT_ENTRY" in block
    assert "truncated" in block


def test_total_budget_caps_block():
    c = _construct(
        priorities="P" * 2000,
        macro_plan="M" * 2000,
        self_model="S" * 2000,
    )
    block = c.as_prompt_block(
        include=("PRIORITIES.md", "MACRO_PLAN.md", "SELF.md"),
        per_doc_max=2000,
        total_max=1500,
    )
    assert len(block) <= 1600  # total cap honoured (allowing marker slack)


def test_empty_docs_are_skipped():
    c = _construct(priorities="real content")
    block = c.as_prompt_block(include=("PRIORITIES.md", "SELF.md", "MACRO_PLAN.md"))
    assert "PRIORITIES.md" in block
    assert "SELF.md" not in block
