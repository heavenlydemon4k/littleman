"""First Light — the bootstrap / re-grounding protocol.

Starting from minimal state, the agent:
  1. seeds the mental construct documents from their templates,
  2. takes inventory of its own skills (the self-model's capability section),
  3. queries external interfaces it owns (wallet/positions, best-effort),
  4. synthesizes an initial PRIORITIES / MACRO_PLAN / SELF from SOUL.md,
  5. writes a bootstrap DIRECTIVE and creates the first heartbeat.

This is invokable at any time, not only at install. If the construct is wiped or the agent
needs to re-ground, calling run() rebuilds the cognitive layer from SOUL.md + live skills +
external state. Existing agent-populated documents are not overwritten unless force=True.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from littleman.config import settings
from littleman.heartbeat import store
from littleman.llm.client import load_soul
from littleman.llm.complete import complete_text
from littleman.llm.prompts import FIRST_LIGHT_DOC_SYSTEM, render
from littleman.meta import construct
from littleman.meta.world_model import WorldModelManager
from littleman.skills.registry import get_registry

# Documents First Light authors via plain-text generation, with the budget for each.
_FL_DOCS = ("PRIORITIES.md", "MACRO_PLAN.md", "SELF.md")


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        # Drop an opening ```lang line and a trailing ``` if present.
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()


async def run(db: AsyncSession, force: bool = False) -> dict:
    # 1. Seed live documents from templates (no-op for docs that already exist).
    if force:
        for name in construct.OVERWRITE_DOCS:
            path = construct._doc_path(name)  # noqa: SLF001 — intentional internal use
            if path.exists():
                path.unlink()
    construct.seed_from_templates()

    # 2. Capability inventory from the live registry.
    registry = get_registry()
    capability_inventory = registry.summary_text()

    # 3. External state (best-effort; wallet APIs may be unconfigured at first light).
    wm = WorldModelManager(db)
    state = await wm.load()
    external_state = {
        "wallet_balance_usdc": state.wallet_balance_usdc,
        "available_balance_usdc": state.available_balance_usdc,
        "open_positions": len(state.open_positions),
        "budget_usdc": settings.budget_usdc,
    }
    soul_excerpt = load_soul()[: settings.bootstrap_max_chars]

    # 4. Author each construct document as plain markdown (no fragile mega-JSON).
    for doc in _FL_DOCS:
        system = render(
            FIRST_LIGHT_DOC_SYSTEM,
            doc_name=doc,
            template=construct.read_template(doc),
            soul_excerpt=soul_excerpt,
            inventory=capability_inventory,
            external_state=json.dumps(external_state),
        )
        body = await complete_text(system, f"Write the {doc} body now.", tier="primary")
        construct.write_doc(doc, _strip_fences(body))

    # 5. Bootstrap directive is deterministic — no LLM call needed, no parse risk.
    bootstrap_directive = {
        "session_type": "FULL_CYCLE",
        "primary_focus": "Establish bearings: survey open markets and form an initial strategy",
        "financial_context": f"Fresh budget of {settings.budget_usdc:.2f} USDC, no open positions.",
        "opportunity_notes": ["Identify markets with researchable edge and clear resolution"],
        "constraint_notes": ["Operate within configured risk limits", "Require a real edge before betting"],
    }
    from littleman.meta.directive import _render_directive_md

    construct.write_doc("DIRECTIVE.md", _render_directive_md(bootstrap_directive))

    # 6. Create the first heartbeat — a FULL_CYCLE session a moment from now.
    first_hb = await store.create_heartbeat(
        db,
        fire_at=datetime.now(timezone.utc) + timedelta(seconds=30),
        reason="First Light bootstrap — initial full cycle",
        session_type="FULL_CYCLE",
        context={"primary_trigger": "first_light", "bootstrap_directive": bootstrap_directive},
        spawned_by=None,
    )

    return {
        "first_light": "complete",
        "construct_seeded": True,
        "first_heartbeat_id": first_hb.id,
        "bootstrap_directive": bootstrap_directive,
    }
