"""Tests for SkillRegistry skill filtering."""

from __future__ import annotations

from littleman.skills.registry import SkillRegistry


def test_registry_subset_keeps_only_named_skills():
    registry = SkillRegistry()
    registry.register(name="a", fn=lambda: None, description="skill a", parameters={})
    registry.register(name="b", fn=lambda: None, description="skill b", parameters={})
    registry.register(name="c", fn=lambda: None, description="skill c", parameters={})

    subset = registry.subset({"a", "c"})
    assert set(subset.names()) == {"a", "c"}
    assert "b" not in subset.names()
