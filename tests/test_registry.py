import sys

import pytest


@pytest.mark.asyncio
async def test_builtin_skills_shadow_openclaw_manifests(tmp_path, monkeypatch):
    """A built-in skill must overwrite any OpenClaw manifest with the same name."""
    from littleman.config import Settings
    from littleman.skills.registry import build_registry

    workspace = tmp_path / "workspace"
    oc_dir = workspace / "openclaw" / "skills"
    oc_dir.mkdir(parents=True)
    (oc_dir / "read_skill_doc.md").write_text(
        "---\nname: read_skill_doc\ndescription: OpenClaw stub.\nregister: true\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "littleman.skills.openclaw_loader.settings",
        Settings(workspace_dir=workspace),
    )

    registry = build_registry()
    result = await registry.dispatch("read_skill_doc", {"name": "read_skill_doc"})
    # The built-in read_skill_doc returns a documentation string; the OpenClaw stub would
    # return an error dictionary.
    assert isinstance(result, str)
    assert "No documentation found" in result or "Read the detailed documentation" in result


def test_platform_mode_does_not_import_polymarket(monkeypatch):
    # Ensure Polymarket modules are not loaded after building the registry in platform mode.
    # Clear any prior import so this test is robust when run alongside Polymarket tests.
    for key in list(sys.modules):
        if key.startswith("littleman.applications.polymarket"):
            del sys.modules[key]

    monkeypatch.setattr("littleman.config.settings.active_application", "littleman.platform")
    from littleman.skills.registry import build_registry
    from littleman.db.connection import AsyncSessionLocal

    build_registry(AsyncSessionLocal)
    assert "littleman.applications.polymarket" not in sys.modules
