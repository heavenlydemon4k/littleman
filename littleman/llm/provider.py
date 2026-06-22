"""LLM provider abstraction.

All of the agent's internal cognition routes through a provider so the same orchestration can
run against:
  - a real LLM (RealProvider -> litellm, any OpenAI-compatible/Anthropic/Ollama backend), or
  - a deterministic ScriptedProvider for tests and offline dry-runs.

The provider is selected by settings.llm_mode ("real" | "fake") and can be overridden in tests
via set_provider(). Streaming chat in the API layer uses completion_kwargs() to pick up the
same endpoint/credentials.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol

import litellm

from littleman.config import settings


def completion_kwargs() -> dict[str, Any]:
    """Endpoint/credential kwargs shared by streaming and non-streaming callers.

    Sourced from the live runtime config (UI-editable), which defaults to .env. When an
    OpenAI-compatible base URL is configured (e.g. Kimi/Moonshot), pass it plus the key to
    litellm. Otherwise rely on provider-native env vars (ANTHROPIC_API_KEY, etc.).
    """
    from littleman.llm import runtime

    return runtime.completion_kwargs()


class LLMProvider(Protocol):
    async def complete(self, model: str, messages: list[dict], **kwargs: Any) -> str: ...


class RealProvider:
    """Routes to litellm. Injects the shared endpoint/credentials for openai-compatible hosts."""

    async def complete(self, model: str, messages: list[dict], **kwargs: Any) -> str:
        merged = {**completion_kwargs(), **kwargs}
        response = await litellm.acompletion(model=model, messages=messages, **merged)
        return response.choices[0].message.content or ""


class ScriptedProvider:
    """Deterministic provider for tests / offline dry-runs.

    Each handler is keyed by a marker substring expected in the system prompt; the first match
    produces the response. This lets the full turn cycle run without any network call. Every
    call is recorded for assertions.
    """

    def __init__(self, handlers: dict[str, Callable[[str, str], str]] | None = None):
        self.handlers = handlers if handlers is not None else default_handlers()
        self.calls: list[dict[str, str]] = []

    async def complete(self, model: str, messages: list[dict], **kwargs: Any) -> str:
        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        user = next((m["content"] for m in messages if m.get("role") == "user"), "")
        self.calls.append({"model": model, "system": system[:120], "user": user[:120]})
        for marker, fn in self.handlers.items():
            if marker in system:
                return fn(system, user)
        return '{"note": "scripted-default", "no_handler_for_system": true}'


# ── Scripted handlers: one canned, schema-valid response per cognitive stage ───

def default_handlers() -> dict[str, Callable[[str, str], str]]:
    import json

    def situation(_s: str, _u: str) -> str:
        return json.dumps({
            "financial_state": {"wallet_balance_usdc": 500, "available_balance_usdc": 500,
                                 "total_pnl": 0, "open_positions_count": 0, "open_exposure_usdc": 0},
            "open_positions": [], "pending_resolutions": [], "watched_markets": [],
            "active_research": [], "scheduled_heartbeats": [], "stale_fields": [],
            "last_session_summary": None, "calibration_notes": None,
        })

    def directive(_s: str, _u: str) -> str:
        return json.dumps({
            "session_type": "RESEARCH",
            "primary_focus": "Scan for an initial high-confidence market to research",
            "secondary_focus": None,
            "financial_context": "Fresh budget of 500 USDC, no open positions.",
            "opportunity_notes": ["Look for politics markets with clear resolution criteria"],
            "constraint_notes": ["Stay within risk limits", "Require >=3pt edge"],
            "explicit_skip": [],
        })

    def plan(_s: str, _u: str) -> str:
        return json.dumps({
            "approach": "Survey open markets, pick one with a researchable edge, gather bearings.",
            "resources_needed": ["scan_markets", "read_from_kb"],
            "risks": ["Thin liquidity", "Ambiguous resolution"],
            "hypotheses": [],
        })

    def turns(_s: str, _u: str) -> str:
        return json.dumps({"turns": [
            {"type": "RESEARCH", "title": "survey-markets",
             "params": {"note": "enumerate candidate markets from KB/world model"}, "depends_on": []},
        ]})

    def strategy(_s: str, _u: str) -> str:
        return json.dumps({
            "goal_tree_mutations": [
                {"action": "create", "node_type": "STRATEGY",
                 "title": "Politics markets with clear resolution criteria",
                 "rationale": "Researchable edge, well-studied base rates", "parent_id": None},
            ],
            "tasks": [
                {"type": "RESEARCH", "title": "survey-markets",
                 "params": {"note": "enumerate candidate markets"}, "depends_on": []},
            ],
        })

    def probability(_s: str, _u: str) -> str:
        return json.dumps({
            "estimated_probability": 0.62, "confidence": "MEDIUM",
            "lower_bound": 0.55, "upper_bound": 0.70,
            "key_factors_for": ["base rate"], "key_factors_against": ["uncertainty"],
            "base_rate_notes": None, "information_gaps": ["latest polling"],
            "recommended_action": "MONITOR", "rationale": "Edge present but confidence moderate.",
        })

    def heartbeat_plan(_s: str, _u: str) -> str:
        return json.dumps({"create": [], "amend": [], "cancel": []})

    def first_light_doc(_s: str, _u: str) -> str:
        # First Light now authors each construct doc as plain markdown.
        return "## Current Summary\n- Establish bearings and survey markets\n\n## P1: First edge\n**Why:** No positions yet.\n"

    # Markers are unique phrases from each system prompt (see llm/prompts.py + plan/turns).
    return {
        "producing a structured situation report": situation,
        "You are the directive engine": directive,
        "You are the plan-formation": plan,
        "You are the turns planner": turns,
        "You are the strategy planner": strategy,
        "structured probability estimation": probability,
        "You are the self-scheduler": heartbeat_plan,
        "writing the body of": first_light_doc,
    }


# ── Provider selection ────────────────────────────────────────────────────────

_override: LLMProvider | None = None
_real: RealProvider | None = None
_fake: ScriptedProvider | None = None


def get_provider() -> LLMProvider:
    """Return the provider for the live runtime mode (real|fake), honouring test overrides."""
    global _real, _fake
    if _override is not None:
        return _override

    from littleman.llm import runtime

    mode = runtime.active().get("mode", "real")
    if mode == "fake":
        _fake = _fake or ScriptedProvider()
        return _fake
    _real = _real or RealProvider()
    return _real


def set_provider(provider: LLMProvider | None) -> None:
    """Override the active provider (tests). Pass None to reset to runtime-based selection."""
    global _override
    _override = provider


def reset_cache() -> None:
    """Drop cached real/fake providers so a runtime config change is picked up."""
    global _real, _fake
    _real = None
    _fake = None
