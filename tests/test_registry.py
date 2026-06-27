import sys


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
