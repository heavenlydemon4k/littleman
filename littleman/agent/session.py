"""Session orchestration — one full planning cycle from heartbeat wake to next heartbeat.

Pipeline (see docs/ARCHITECTURE.md §12):
    1. load world model + heartbeat context
    2. (first light if the construct is uninitialised)
    3. synthesize situation report           (meta/synthesizer)
    4. generate directive                     (meta/directive -> writes DIRECTIVE.md)
    5. plan strategy + tasks                  (macro/strategy -> mutates goal tree)
    6. execute task tree                      (tasks/executor, serial, risk-gated)
    7. update world model + append reflection
    8. plan + schedule future heartbeats      (meta/planner / self-scheduler)
    9. mark heartbeat DONE, write session row

Runnable as a module: `python -m littleman.agent.session --boot` to force First Light.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from littleman.agent.lock import SessionLock
from littleman.db.connection import AsyncSessionLocal, init_db
from littleman.db.models import AgentSession
from littleman.heartbeat import store
from littleman.macro import strategy
from littleman.macro.risk import RiskGovernor
from littleman.meta import construct, directive, first_light, planner, synthesizer
from littleman.meta.world_model import WorldModelManager
from littleman.skills.registry import build_registry, get_registry
from littleman.tasks.executor import ExecutionContext, run_tree
from littleman.tasks.tree import TaskTree


async def run_session(
    heartbeat_id: str | None = None,
    boot: bool = False,
    lock_timeout: float = 0.0,
    manual_context: dict | None = None,
) -> dict:
    """Run one session. If heartbeat_id is given, that heartbeat's context drives it; a
    manual_context (from the UI 'run a brief directive session' input) seeds the situation
    for an ad-hoc run.

    Guarded by a cross-process SessionLock so capital is always evaluated against one
    consistent view, even if the scheduler and a manual run overlap (ADR 0001).
    """
    async with SessionLock(timeout=lock_timeout):
        return await _run_session_locked(heartbeat_id, boot, manual_context or {})


async def _run_session_locked(
    heartbeat_id: str | None, boot: bool, manual_context: dict
) -> dict:
    session_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc)

    # The registry needs a session factory so skills can open their own DB sessions.
    build_registry(db_session_factory=AsyncSessionLocal)

    async with AsyncSessionLocal() as db:
        heartbeat_context: dict = dict(manual_context)
        if heartbeat_id:
            hb = await store.get_heartbeat(db, heartbeat_id)
            if hb:
                heartbeat_context = hb.context or {}
                await store.mark_running(db, heartbeat_id)

        try:
            # First Light if needed (or forced via --boot).
            if boot or not construct.is_initialised():
                await first_light.run(db, force=boot)
                # First Light created the first heartbeat; if this was a bare boot with no
                # heartbeat to act on, we stop here and let the scheduler take over.
                if heartbeat_id is None:
                    return await _finish(
                        db, session_id, started, heartbeat_id,
                        directive_payload={"session_type": "FIRST_LIGHT"},
                        exec_result={"bets_placed": 0, "research_calls": 0},
                        hb_plan={"created": []},
                        summary="First Light complete; first heartbeat scheduled.",
                    )

            result = await _run_pipeline(db, session_id, heartbeat_id, heartbeat_context)
            if heartbeat_id:
                await store.mark_done(db, heartbeat_id)
            return result

        except Exception as e:  # noqa: BLE001 — a failed session must mark its heartbeat
            if heartbeat_id:
                await store.mark_failed(db, heartbeat_id, str(e))
            raise


async def _run_pipeline(
    db: AsyncSession, session_id: str, heartbeat_id: str | None, heartbeat_context: dict
) -> dict:
    wm = WorldModelManager(db)
    state = await wm.load()

    # 3-4. Situation -> directive (directive engine writes DIRECTIVE.md).
    situation = await synthesizer.synthesize(state, heartbeat_context)
    directive_payload = await directive.generate(situation)

    # 5. Strategy + task plan.
    plan = await strategy.plan(db, directive_payload)
    tree = TaskTree.from_specs(plan["tasks"])

    # 6. Execute (serial, risk-gated).
    ctx = ExecutionContext(
        db=db,
        registry=get_registry(),
        governor=RiskGovernor(),
        wm=wm,
        session_id=session_id,
    )
    exec_result = await run_tree(ctx, tree)

    # 7. Update world model + append a reflection entry.
    summary = (
        f"{directive_payload.get('session_type')}: "
        f"{exec_result['bets_placed']} bets, {exec_result['research_calls']} research calls, "
        f"{exec_result['tree']['done']}/{exec_result['tree']['total']} tasks done"
    )
    state = await wm.load()
    state.last_session_summary = summary
    await wm.save(state)
    construct.append_reflection(
        f"## {datetime.now(timezone.utc).date().isoformat()} — session {session_id[:8]}\n"
        f"**Context:** {directive_payload.get('primary_focus', '')}\n"
        f"**Outcome:** {summary}\n"
    )

    # 8. Self-scheduler plans future heartbeats.
    hb_plan = await planner.plan_and_schedule(
        db, state, session_summary=summary, spawned_by=heartbeat_id
    )

    return await _finish(
        db, session_id, datetime.now(timezone.utc), heartbeat_id,
        directive_payload, exec_result, hb_plan, summary,
    )


async def _finish(
    db, session_id, started, heartbeat_id, directive_payload, exec_result, hb_plan, summary
) -> dict:
    row = AgentSession(
        id=session_id,
        heartbeat_id=heartbeat_id,
        directive=directive_payload,
        bets_placed=exec_result.get("bets_placed", 0),
        research_calls=exec_result.get("research_calls", 0),
        heartbeats_created=len(hb_plan.get("created", [])),
        ended_at=datetime.now(timezone.utc),
        outcome_summary=summary,
    )
    db.add(row)
    await db.commit()

    # Narrate this run into the Main session so it is visible in the chat list.
    from littleman.agent.mainlog import log_main

    trigger = "autonomous wake" if heartbeat_id else "manual run"
    focus = (directive_payload or {}).get("primary_focus", "")
    narration = (
        f"**{(directive_payload or {}).get('session_type', 'SESSION')}** · {trigger}\n\n"
        + (f"Focus: {focus}\n\n" if focus else "")
        + f"{summary}"
    )
    try:
        await log_main(db, narration)
    except Exception:  # noqa: BLE001 — narration must never fail a session
        pass

    return {
        "session_id": session_id,
        "summary": summary,
        "heartbeats_created": len(hb_plan.get("created", [])),
    }


def _main() -> None:
    parser = argparse.ArgumentParser(description="Run one Littleman session")
    parser.add_argument("--boot", action="store_true", help="Force First Light bootstrap")
    parser.add_argument("--heartbeat-id", default=None, help="Heartbeat id driving this session")
    args = parser.parse_args()

    async def _run() -> None:
        await init_db()
        result = await run_session(heartbeat_id=args.heartbeat_id, boot=args.boot)
        print(result)

    asyncio.run(_run())


if __name__ == "__main__":
    _main()
