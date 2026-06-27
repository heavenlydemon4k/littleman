"""Tests for the expanded construct docs (HYPOTHESES, BLOCKERS, SKILL_NOTES)."""

from __future__ import annotations

import pytest

from littleman.meta import construct


NEW_DOCS = ("HYPOTHESES.md", "BLOCKERS.md", "SKILL_NOTES.md")


def test_new_docs_are_overwrite_docs():
    for name in NEW_DOCS:
        assert name in construct.OVERWRITE_DOCS


def test_new_docs_are_in_all_docs():
    for name in NEW_DOCS:
        assert name in construct.ALL_DOCS


def test_new_docs_not_in_first_light_docs():
    for name in NEW_DOCS:
        assert name not in construct.FIRST_LIGHT_DOCS


def test_construct_fields_exist():
    c = construct.Construct(
        priorities="",
        macro_plan="",
        self_model="",
        exposure="",
        calendar="",
        directive="",
        turns="",
        hypotheses="h",
        blockers="b",
        skill_notes="s",
        reflection="",
    )
    assert c.hypotheses == "h"
    assert c.blockers == "b"
    assert c.skill_notes == "s"


def test_load_reads_new_docs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        construct.settings, "workspace_dir", tmp_path
    )
    construct_dir = tmp_path / "construct"
    construct_dir.mkdir()
    for name in NEW_DOCS:
        (construct_dir / name).write_text(f"body of {name}", encoding="utf-8")
    # Seed the first-light docs so load() succeeds.
    for name in construct.FIRST_LIGHT_DOCS:
        (construct_dir / name).write_text("", encoding="utf-8")

    c = construct.load()
    assert c.hypotheses == "body of HYPOTHESES.md"
    assert c.blockers == "body of BLOCKERS.md"
    assert c.skill_notes == "body of SKILL_NOTES.md"


def test_as_prompt_block_includes_new_docs():
    c = construct.Construct(
        priorities="",
        macro_plan="",
        self_model="",
        exposure="",
        calendar="",
        directive="",
        turns="",
        hypotheses="## Active\n- test",
        blockers="## Current\n- blocker",
        skill_notes="## Skills\n- note",
        reflection="",
    )
    block = c.as_prompt_block(per_doc_max=1000, total_max=10_000)
    for name in NEW_DOCS:
        assert f"===== {name} =====" in block


def test_write_doc_allows_new_docs(tmp_path, monkeypatch):
    monkeypatch.setattr(construct.settings, "workspace_dir", tmp_path)
    for name in NEW_DOCS:
        construct.write_doc(name, f"written {name}")
        assert (tmp_path / "construct" / name).read_text(encoding="utf-8") == f"written {name}"


def test_templates_exist():
    for name in NEW_DOCS:
        template = construct.read_template(name)
        assert "TEMPLATE" in template
