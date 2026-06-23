"""Construct file skills — the agent reads/writes its own cognition, safely scoped."""

import pytest

from littleman.config import settings
from littleman.meta import construct
from littleman.skills.construct_skills import make_construct_skills


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    ws = tmp_path / "workspace"
    (ws / "construct").mkdir(parents=True)
    for name in construct.ALL_DOCS:
        stem = name.replace(".md", "")
        (ws / "construct" / f"{stem}.template.md").write_text(f"<!-- {name} template -->\n", encoding="utf-8")
    (ws / "SOUL.md").write_text("# SOUL\nMission: test.", encoding="utf-8")
    (ws / "AGENT.md").write_text("# AGENT\nOperating manual.", encoding="utf-8")
    monkeypatch.setattr(settings, "workspace_dir", ws)
    construct.seed_from_templates()
    return ws


def _skill(name):
    return {s["name"]: s["fn"] for s in make_construct_skills()}[name]


@pytest.mark.asyncio
async def test_read_static_and_construct_docs(workspace):
    read = _skill("read_construct")
    assert "Mission: test" in (await read("SOUL.md"))["content"]
    assert "Operating manual" in (await read("AGENT.md"))["content"]
    assert (await read("PRIORITIES.md"))["doc"] == "PRIORITIES.md"


@pytest.mark.asyncio
async def test_read_unknown_doc_is_refused(workspace):
    read = _skill("read_construct")
    r = await read("../../etc/passwd")
    assert "error" in r
    assert "readable" in r


@pytest.mark.asyncio
async def test_write_construct_overwrite_doc(workspace):
    write = _skill("write_construct")
    read = _skill("read_construct")
    res = await write("PRIORITIES.md", "## Current Summary\n- do the thing\n")
    assert res["written"] is True
    assert "do the thing" in (await read("PRIORITIES.md"))["content"]


@pytest.mark.asyncio
async def test_write_refuses_soul_and_reflection(workspace):
    write = _skill("write_construct")
    soul = await write("SOUL.md", "hacked")
    assert "error" in soul
    refl = await write("REFLECTION.md", "nope")
    assert "error" in refl


@pytest.mark.asyncio
async def test_append_reflection(workspace):
    append = _skill("append_reflection")
    read = _skill("read_construct")
    await append("## entry one")
    await append("## entry two")
    body = (await read("REFLECTION.md"))["content"]
    assert "entry one" in body and "entry two" in body


@pytest.mark.asyncio
async def test_read_template_and_list(workspace):
    tmpl = await _skill("read_template")("SELF.md")
    assert "template" in tmpl
    listing = await _skill("list_workspace")()
    assert "SOUL.md" in listing["readable"]
    assert "PRIORITIES.md" in listing["writable"]
    assert listing["append_only"] == ["REFLECTION.md"]
