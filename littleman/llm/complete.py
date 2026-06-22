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

import litellm

from littleman.config import settings


def _model_for(tier: str) -> str:
    return settings.llm_secondary_model if tier == "secondary" else settings.llm_primary_model


def _extract_json(text: str) -> Any:
    """Parse JSON from a model response, tolerating markdown fences and surrounding prose."""
    text = text.strip()
    # Strip ```json ... ``` fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.S)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fall back to the first balanced {...} or [...] block.
        for opener, closer in (("{", "}"), ("[", "]")):
            start = text.find(opener)
            end = text.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    continue
        raise


async def complete_text(
    system: str,
    user: str,
    tier: str = "primary",
    **kwargs: Any,
) -> str:
    response = await litellm.acompletion(
        model=_model_for(tier),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **kwargs,
    )
    return response.choices[0].message.content or ""


async def complete_json(
    system: str,
    user: str,
    tier: str = "primary",
    **kwargs: Any,
) -> Any:
    raw = await complete_text(system, user, tier=tier, **kwargs)
    return _extract_json(raw)
