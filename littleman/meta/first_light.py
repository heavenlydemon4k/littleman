"""First Light — the bootstrap / re-grounding protocol.

First Light is the agent's first-ever wake (and a re-invokable re-situate capability). It is
*agentic*: the agent reads its own files (AGENT.md, SOUL.md, onboarding answers, templates) and
writes its construct (PRIORITIES/MACRO_PLAN/SELF) through its construct skills, then greets the
operator. A deterministic safety net guarantees a usable construct even if a weak model skips a
document. In fake mode (tests / offline), the deterministic authoring is used directly.

See docs/design/first-light-and-self-onboarding.md.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from littleman.config import settings
from littleman.heartbeat import store
from littleman.llm import runtime
from littleman.llm.client import load_agent_manual, load_soul
from littleman.llm.complete import complete_text
from littleman.llm.prompts import FIRST_LIGHT_DOC_SYSTEM, render
from littleman.meta import construct
from littleman.meta.world_model import WorldModelManager

# Documents First Light must produce.
_FL_DOCS = ("PRIORITIES.md", "MACRO_PLAN.md", "SELF.md")


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()


async def _onboarding_block(db: AsyncSession) -> str:
    from littleman.db.models import Profile

    prof = (await db.execute(select(Profile).where(Profile.id == 1))).scalar_one_or_none()
    if not prof:
        return "(no onboarding profile; infer the mission from SOUL.md)"
    lines = [
        f"Operator name: {prof.display_name or 'unknown'}",
        f"Stated purpose: {prof.purpose or '(see SOUL.md)'}",
        f"Onboarding path: {prof.onboarding_path or 'unknown'}",
    ]
    answers = prof.answers or {}
    labels = {
        "objective": "Objective and success",
        "focus": "Focus (prioritize / avoid)",
        "constraints": "Constraints / red lines",
        "red_lines": "Constraints / red lines",
        "autonomy": "Autonomy and check-in",
    }
    given = [(labels.get(k, k), str(v).strip()) for k, v in answers.items() if str(v).strip()]
    if given:
        lines.append("Guided answers:")
        lines += [f"- {label}: {val}" for label, val in given]
    lines.append(
        "Interpret these answers richly and coherently when forming your priorities, plan, and "
        "self-model — turn them into concrete operating intent, do not merely restate them."
    )
    return "\n".join(lines)


def _inventory() -> str:
    from littleman.skills.registry import build_registry, get_registry

    try:
        return get_registry().summary_text()
    except RuntimeError:
        from littleman.db.connection import AsyncSessionLocal

        return build_registry(AsyncSessionLocal).summary_text()


async def _author_doc_scripted(doc: str, soul: str, inventory: str, external_state: dict) -> None:
    """Deterministic per-doc authoring (the safety net + fake-mode path)."""
    system = render(
        FIRST_LIGHT_DOC_SYSTEM,
        doc_name=doc,
        template=construct.read_template(doc),
        soul_excerpt=soul[: settings.bootstrap_max_chars],
        inventory=inventory,
        external_state=json.dumps(external_state),
    )
    body = await complete_text(system, f"Write the {doc} body now.", tier="primary")
    construct.write_doc(doc, _strip_fences(body))


def _doc_is_empty(doc: str) -> bool:
    c = construct.load()
    mapping = {"PRIORITIES.md": c.priorities, "MACRO_PLAN.md": c.macro_plan, "SELF.md": c.self_model}
    return not (mapping.get(doc, "") or "").strip()


async def _agentic_first_light(db: AsyncSession, soul: str, inventory: str, external_state: dict) -> str:
    """Run First Light as an agentic ReAct wake; return the agent's greeting."""
    from littleman.agent.loop import run as react_run
    from littleman.skills.registry import build_registry, get_registry

    try:
        registry = get_registry()
    except RuntimeError:
        from littleman.db.connection import AsyncSessionLocal

        registry = build_registry(AsyncSessionLocal)

    onboarding = await _onboarding_block(db)
    manual = load_agent_manual()

    system = (
        f"{manual}\n\n"
        f"===== SOUL.md (your identity and mission) =====\n{soul[: settings.bootstrap_max_chars]}\n\n"
        f"===== Your onboarding answers =====\n{onboarding}\n\n"
        f"===== Your skills =====\n{inventory}\n\n"
        f"===== Current external state =====\n{json.dumps(external_state)}\n\n"
        "This is FIRST LIGHT — your first wake. You have no prior context beyond these files.\n"
        "Do, in order:\n"
        "1. Use read_construct / read_template to see the format of each construct document.\n"
        "2. Author your starting PRIORITIES.md, MACRO_PLAN.md and SELF.md with write_construct. "
        "SELF.md must inventory the skills you actually have and note you have no track record yet. "
        "Be concrete and specific to THIS operator and mission, never generic.\n"
        "3. When your construct is written, STOP calling tools and reply with your greeting to the "
        "operator: introduce yourself, state your understanding of the mission in your own words, "
        "name your initial priorities, and ask anything you genuinely need clarified."
    )
    user = "Begin First Light now. Read your files, author your construct, then greet the operator."

    result = await react_run(system, user, registry, max_iterations=10)
    return result.final_text.strip()


async def run(db: AsyncSession, force: bool = False) -> dict:
    # 1. Seed construct documents from templates (clearing existing ones if forced).
    if force:
        for name in construct.OVERWRITE_DOCS:
            path = construct._doc_path(name)  # noqa: SLF001 — intentional internal use
            if path.exists():
                path.unlink()
    construct.seed_from_templates()

    inventory = _inventory()
    soul = load_soul()

    wm = WorldModelManager(db)
    state = await wm.load()
    external_state = {
        "wallet_balance_usdc": state.wallet_balance_usdc,
        "available_balance_usdc": state.available_balance_usdc,
        "open_positions": len(state.open_positions),
        "budget_usdc": settings.budget_usdc,
    }

    greeting = ""
    mode = runtime.active().get("mode", "real")

    if mode == "fake":
        # Offline / tests: deterministic authoring, no ReAct (the scripted provider has no tools).
        for doc in _FL_DOCS:
            await _author_doc_scripted(doc, soul, inventory, external_state)
        greeting = "First Light complete. I have formed my initial bearings."
    else:
        # Agentic: the agent reads and writes its own files, then greets.
        greeting = await _agentic_first_light(db, soul, inventory, external_state)
        # Safety net: guarantee every required doc exists even if the agent skipped one.
        for doc in _FL_DOCS:
            if _doc_is_empty(doc):
                await _author_doc_scripted(doc, soul, inventory, external_state)

    # Bootstrap directive (deterministic) + first heartbeat.
    bootstrap_directive = {
        "session_type": "FULL_CYCLE",
        "primary_focus": "Establish bearings and act on the mission",
        "financial_context": f"Budget {settings.budget_usdc:.2f} USDC.",
        "opportunity_notes": [],
        "constraint_notes": ["Operate within configured hard limits"],
    }
    from littleman.meta.directive import _render_directive_md

    construct.write_doc("DIRECTIVE.md", _render_directive_md(bootstrap_directive))

    first_hb = await store.create_heartbeat(
        db,
        fire_at=datetime.now(timezone.utc) + timedelta(seconds=30),
        reason="First Light bootstrap — initial full cycle",
        session_type="FULL_CYCLE",
        context={"primary_trigger": "first_light", "bootstrap_directive": bootstrap_directive},
        spawned_by=None,
    )

    # Narrate the greeting into the Main session so the operator sees it in chat.
    if greeting:
        from littleman.agent.mainlog import log_main

        try:
            await log_main(db, greeting)
        except Exception:  # noqa: BLE001 — narration must not fail First Light
            pass

    return {
        "first_light": "complete",
        "mode": mode,
        "greeting": greeting,
        "first_heartbeat_id": first_hb.id,
        "bootstrap_directive": bootstrap_directive,
    }
