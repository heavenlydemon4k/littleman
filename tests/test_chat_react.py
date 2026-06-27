"""Tests for chat ReAct tool execution and chat-safe skill filtering."""

from __future__ import annotations

import pytest

from littleman.skills.registry import SkillRegistry


@pytest.fixture
def registry():
    reg = SkillRegistry()

    async def safe_skill(query: str) -> dict:
        return {"ok": True, "query": query}

    async def risky_skill() -> dict:
        return {"ok": True}

    reg.register(
        name="safe_skill",
        fn=safe_skill,
        description="A safe chat skill.",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    )
    reg.register(
        name="risky_skill",
        fn=risky_skill,
        description="A risky skill.",
        parameters={"type": "object", "properties": {}},
        chat_safe=False,
    )
    return reg


def test_get_chat_definitions_excludes_unsafe(registry):
    all_defs = registry.get_definitions()
    chat_defs = registry.get_chat_definitions()

    all_names = {d["function"]["name"] for d in all_defs}
    chat_names = {d["function"]["name"] for d in chat_defs}

    assert "safe_skill" in all_names
    assert "risky_skill" in all_names
    assert "safe_skill" in chat_names
    assert "risky_skill" not in chat_names


def test_skill_dataclass_has_chat_safe():
    from littleman.skills.registry import Skill

    s = Skill(name="x", fn=lambda: None, description="d", parameters={}, chat_safe=False)
    assert s.chat_safe is False


@pytest.mark.asyncio
async def test_execute_chat_tool(registry):
    from littleman.api.routes.chat import _execute_chat_tool

    # Ensure the registry is the one we set up.
    from littleman.skills import registry as registry_module

    registry_module._registry = registry

    result = await _execute_chat_tool({"name": "safe_skill", "args": {"query": "hello"}})
    assert result == {"ok": True, "query": "hello"}


@pytest.mark.asyncio
async def test_execute_chat_tool_returns_error_on_unknown(registry):
    from littleman.api.routes.chat import _execute_chat_tool
    from littleman.skills import registry as registry_module

    registry_module._registry = registry

    result = await _execute_chat_tool({"name": "missing_skill", "args": {}})
    assert "error" in result
