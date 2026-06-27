async def test_read_skill_doc_resolves_by_registered_name(tmp_path, monkeypatch):
    from littleman.config import Settings
    from littleman.skills.skill_docs import read_skill_doc

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "kb.md").write_text(
        "---\nskills:\n  - write_to_kb\n  - read_from_kb\n  - search_kb\n---\n# KB docs\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "littleman.skills.skill_docs.settings",
        Settings(workspace_dir=tmp_path),
    )

    result = await read_skill_doc("write_to_kb")
    assert "KB docs" in result

    result = await read_skill_doc("read_from_kb")
    assert "KB docs" in result
