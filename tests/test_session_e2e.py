"""End-to-end pipeline test with the scripted LLM provider.

Exercises the real cognition functions — synthesize → directive → strategy → execute → plan
heartbeats — against an in-memory DB and a temp workspace, with no network. This guards the
full turn cycle that the CLI `boot`/`once` commands run.
"""

import pytest

from littleman.config import settings
from littleman.llm.provider import ScriptedProvider, set_provider
from littleman.meta import construct


@pytest.fixture
def fake_env(tmp_path, monkeypatch):
    ws = tmp_path / "workspace"
    (ws / "construct").mkdir(parents=True)
    for name in construct.ALL_DOCS:
        stem = name.replace(".md", "")
        (ws / "construct" / f"{stem}.template.md").write_text(
            f"<!-- TEMPLATE {name} -->\n", encoding="utf-8"
        )
    (ws / "SOUL.md").write_text("You are Littleman. Mission: test the loop.", encoding="utf-8")
    (ws / "SKILLS.md").write_text("Skills available.", encoding="utf-8")
    monkeypatch.setattr(settings, "workspace_dir", ws)
    monkeypatch.setattr(settings, "llm_mode", "fake")
    set_provider(ScriptedProvider())
    construct.seed_from_templates()
    yield ws
    set_provider(None)


@pytest.mark.asyncio
async def test_full_turn_cycle(db, fake_env):
    from littleman.macro import strategy
    from littleman.macro.risk import RiskGovernor
    from littleman.meta import directive, planner, synthesizer
    from littleman.meta.world_model import WorldModelManager
    from littleman.skills.registry import build_registry, get_registry
    from littleman.tasks.executor import ExecutionContext, run_tree
    from littleman.tasks.tree import TaskTree

    build_registry(db_session_factory=None)
    wm = WorldModelManager(db)
    state = await wm.load()

    # SITUATE
    situation = await synthesizer.synthesize(state, {})
    assert "financial_state" in situation

    # DIRECTIVE (also writes DIRECTIVE.md)
    d = await directive.generate(situation)
    assert d["session_type"] == "RESEARCH"
    assert (fake_env / "construct" / "DIRECTIVE.md").read_text().strip()

    # STRATEGY → tasks + goal-tree mutation
    plan = await strategy.plan(db, d)
    assert len(plan["tasks"]) >= 1

    # EXECUTE
    tree = TaskTree.from_specs(plan["tasks"])
    ctx = ExecutionContext(
        db=db, registry=get_registry(), governor=RiskGovernor(), wm=wm, session_id="test-sess"
    )
    result = await run_tree(ctx, tree)
    assert result["tree"]["total"] >= 1
    assert result["tree"]["failed"] == 0

    # SCHEDULE — self-scheduler creates at least one future heartbeat
    hb_plan = await planner.plan_and_schedule(
        db, state, session_summary="test", spawned_by=None, use_llm_refinement=False
    )
    assert len(hb_plan["created"]) >= 1


@pytest.mark.asyncio
async def test_directive_persists_to_construct(db, fake_env):
    from littleman.meta import directive, synthesizer
    from littleman.meta.world_model import WorldModelManager

    state = await WorldModelManager(db).load()
    situation = await synthesizer.synthesize(state, {})
    await directive.generate(situation)

    directive_md = (fake_env / "construct" / "DIRECTIVE.md").read_text()
    assert "RESEARCH" in directive_md
    assert "primary focus" in directive_md.lower()
