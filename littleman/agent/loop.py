"""ReAct loop — reason + act until the model stops calling tools.

Used for open-ended, skill-driven sub-tasks where the next action depends on the result of
the previous one (e.g. a research task that decides what to fetch next based on what it just
read). The structured session pipeline (meta -> macro -> task) is the top-level driver; this
loop is a reusable executor for steps inside it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import litellm

from littleman.llm import runtime
from littleman.llm.provider import completion_kwargs
from littleman.skills.registry import SkillRegistry

_MAX_ITERATIONS = 6


@dataclass
class LoopResult:
    final_text: str
    transcript: list[dict[str, Any]] = field(default_factory=list)
    tool_invocations: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0


async def run(
    system: str,
    user: str,
    registry: SkillRegistry,
    model: str | None = None,
    max_iterations: int = _MAX_ITERATIONS,
) -> LoopResult:
    model = model or runtime.model_for("primary")
    tools = registry.get_definitions()
    extra = completion_kwargs()  # Kimi/OpenAI-compatible endpoint + key
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    result = LoopResult(final_text="")

    for i in range(max_iterations):
        result.iterations = i + 1
        response = await litellm.acompletion(
            model=model, messages=messages, tools=tools, **extra
        )
        choice = response.choices[0]
        msg = choice.message

        messages.append(msg.model_dump() if hasattr(msg, "model_dump") else dict(msg))

        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            result.final_text = msg.content or ""
            break

        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                output = await registry.dispatch(name, args)
            except Exception as e:  # noqa: BLE001 — surface tool errors back to the model
                output = {"error": str(e)}

            result.tool_invocations.append({"name": name, "args": args, "output": output})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(output, default=str),
                }
            )

    result.transcript = messages
    return result
