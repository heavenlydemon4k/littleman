"""Situation synthesizer — world model -> structured situation report.

This is the first cognitive step of a session. It describes the current situation; it does
not plan or decide. The output feeds the directive engine.
"""

from __future__ import annotations

import json
from typing import Any

from littleman.llm.complete import complete_json
from littleman.llm.prompts import SITUATION_REPORT_PROMPT
from littleman.meta.world_model import WorldModelState


def _world_model_payload(state: WorldModelState, heartbeat_context: dict | None) -> dict[str, Any]:
    return {
        "financial_state": {
            "wallet_balance_usdc": state.wallet_balance_usdc,
            "available_balance_usdc": state.available_balance_usdc,
            "total_pnl": state.total_pnl,
            "open_positions_count": len(state.open_positions),
            "open_exposure_usdc": state.open_exposure_usdc(),
        },
        "open_positions": [p.model_dump() for p in state.open_positions],
        "pending_resolutions": [p.model_dump() for p in state.pending_resolutions],
        "watched_markets": state.watched_markets,
        "active_research_topics": state.active_research_topics,
        "scheduled_heartbeats": [h.model_dump() for h in state.next_heartbeats],
        "stale_fields": state.stale_fields(),
        "last_session_summary": state.last_session_summary,
        "calibration_by_category": state.calibration_by_category,
        "circuit_breaker_active": state.circuit_breaker_active,
        "heartbeat_context": heartbeat_context or {},
    }


async def synthesize(
    state: WorldModelState,
    heartbeat_context: dict | None = None,
) -> dict[str, Any]:
    payload = _world_model_payload(state, heartbeat_context)
    prompt = SITUATION_REPORT_PROMPT.format(world_model_json=json.dumps(payload, indent=2))
    # The situation report is descriptive; the secondary model tier is adequate.
    report = await complete_json(prompt, "Produce the situation report now.", tier="secondary")
    return report
