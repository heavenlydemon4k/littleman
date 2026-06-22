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
from littleman.llm.complete import complete_json
from littleman.meta import construct
from littleman.meta.world_model import WorldModelManager
from littleman.skills.registry import get_registry

FIRST_LIGHT_SYSTEM = """You are performing First Light for Littleman, an autonomous Polymarket
trading agent. You are populating your own cognitive scaffolding from your prime directive
(SOUL.md), your capability inventory, and your current external state.

Output valid JSON (no markdown fences):
{
  "priorities_md": string,   // full markdown body for PRIORITIES.md (ranked, with a Current Summary)
  "macro_plan_md": string,   // full markdown body for MACRO_PLAN.md (initial campaigns)
  "self_md": string,         // full markdown body for SELF.md (capabilities, limitations, empty calibration)
  "bootstrap_directive": {
    "session_type": "FULL_CYCLE",
    "primary_focus": string,
    "financial_context": string,
    "opportunity_notes": [string],
    "constraint_notes": [string]
  }
}

Honour the format instructions embedded as HTML comments in each template. Be concrete: use
the actual budget, the actual skills, and the actual constraints. Calibration starts empty —
you have no track record yet."""


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

    # 4. Synthesize the initial construct from SOUL.md + inventory + external state.
    user = (
        f"SOUL.md (prime directive and domain knowledge):\n{load_soul()}\n\n"
        f"PRIORITIES.md template:\n{construct.read_template('PRIORITIES.md')}\n\n"
        f"MACRO_PLAN.md template:\n{construct.read_template('MACRO_PLAN.md')}\n\n"
        f"SELF.md template:\n{construct.read_template('SELF.md')}\n\n"
        f"Capability inventory (your registered skills):\n{capability_inventory}\n\n"
        f"Current external state:\n{json.dumps(external_state, indent=2)}\n\n"
        "Produce the First Light JSON now."
    )
    result = await complete_json(FIRST_LIGHT_SYSTEM, user, tier="primary")

    # 5. Write the populated construct documents.
    construct.write_doc("PRIORITIES.md", result.get("priorities_md", ""))
    construct.write_doc("MACRO_PLAN.md", result.get("macro_plan_md", ""))
    construct.write_doc("SELF.md", result.get("self_md", ""))

    bootstrap_directive = result.get("bootstrap_directive", {})
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
