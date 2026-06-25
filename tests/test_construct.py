"""Mental construct tests — seeding, overwrite vs append, prompt rendering."""

import pytest

from littleman.config import settings
from littleman.meta import construct


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    ws = tmp_path / "workspace"
    (ws / "construct").mkdir(parents=True)
    # Provide minimal templates.
    for name in construct.ALL_DOCS:
        stem = name.replace(".md", "")
        (ws / "construct" / f"{stem}.template.md").write_text(
            f"<!-- TEMPLATE {name} -->\n", encoding="utf-8"
        )
    monkeypatch.setattr(settings, "workspace_dir", ws)
    return ws


def test_not_initialised_before_seeding(temp_workspace):
    assert construct.is_initialised() is False


def test_seed_from_templates_creates_live_docs(temp_workspace):
    construct.seed_from_templates()
    assert construct.is_initialised() is True
    for name in construct.OVERWRITE_DOCS:
        assert (temp_workspace / "construct" / name).exists()


def test_write_doc_overwrites(temp_workspace):
    construct.seed_from_templates()
    construct.write_doc("PRIORITIES.md", "## Current Summary\n- one thing\n")
    loaded = construct.load()
    assert "one thing" in loaded.priorities


def test_append_reflection_grows(temp_workspace):
    construct.seed_from_templates()
    construct.append_reflection("## entry one")
    construct.append_reflection("## entry two")
    loaded = construct.load()
    assert "entry one" in loaded.reflection
    assert "entry two" in loaded.reflection


def test_write_doc_rejects_append_only_doc(temp_workspace):
    construct.seed_from_templates()
    with pytest.raises(ValueError):
        construct.write_doc("REFLECTION.md", "nope")


def test_prompt_block_selects_documents(temp_workspace):
    construct.seed_from_templates()
    construct.write_doc("PRIORITIES.md", "PRIO_CONTENT")
    construct.write_doc("SELF.md", "SELF_CONTENT")
    block = construct.load().as_prompt_block(include=("PRIORITIES.md",))
    assert "PRIO_CONTENT" in block
    assert "SELF_CONTENT" not in block


def test_seed_does_not_clobber_existing(temp_workspace):
    construct.seed_from_templates()
    construct.write_doc("PRIORITIES.md", "AGENT_WRITTEN")
    construct.seed_from_templates()  # second call must not overwrite
    assert "AGENT_WRITTEN" in construct.load().priorities
