"""Centralised LLM completion helpers for the agent's internal reasoning.

The chat UI streams directly via litellm in the API layer. The agent's internal cognitive
calls (directive generation, strategy planning, probability estimation) are non-streaming and
expect structured output, so they go through these helpers, which handle model-tier selection
and tolerant JSON parsing.
"""

from __future__ import annotations

import json
import re
from typing import Any

from littleman.llm.provider import get_provider
from littleman.llm import runtime


def _model_for(tier: str) -> str:
    return runtime.model_for(tier)


def _extract_json(text: str) -> Any:
    """Parse JSON from a model response, tolerating markdown fences and surrounding prose.

    strict=False permits raw control characters (newlines, tabs) inside string values, which
    real models routinely emit when a JSON field holds multi-line markdown — the common case
    that broke First Light.
    """
    text = text.strip()
    # Strip ```json ... ``` fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.S)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        # Fall back to the first balanced {...} or [...] block.
        for opener, closer in (("{", "}"), ("[", "]")):
            start = text.find(opener)
            end = text.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1], strict=False)
                except json.JSONDecodeError:
                    continue
        raise


async def complete_text(
    system: str,
    user: str,
    tier: str = "primary",
    **kwargs: Any,
) -> str:
    provider = get_provider()
    # Default a generous output cap so structured/markdown responses are not truncated
    # mid-JSON (the truncation that broke First Light). Callers may override.
    kwargs.setdefault("max_tokens", 4096)
    return await provider.complete(
        model=_model_for(tier),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **kwargs,
    )


async def complete_json(
    system: str,
    user: str,
    tier: str = "primary",
    **kwargs: Any,
) -> Any:
    raw = await complete_text(system, user, tier=tier, **kwargs)
    return _extract_json(raw)
