import pytest

from littleman.applications import Application, get_active_application


class StubApp(Application):
    name = "stub"

    def is_configured(self):
        return True

    def register_skills(self, registry, db_session_factory=None):
        pass

    async def reconcile(self, db):
        return {}

    async def execute(self, ctx, node):
        return {}

    def dashboard_status(self):
        return {}

    def root_goal(self):
        return {"title": "stub", "rationale": "stub"}


@pytest.mark.asyncio
async def test_application_first_light_context_defaults_to_empty():
    app = StubApp()
    assert await app.first_light_context() == {}


def test_platform_application_loads_by_default():
    app = get_active_application()
    assert app is not None
    assert app.name == "littleman.platform"
    assert app.is_configured() is True


@pytest.mark.asyncio
async def test_platform_application_first_light_context_is_generic():
    app = get_active_application()
    ctx = await app.first_light_context()
    assert "wallet_balance_usdc" not in ctx
    assert "open_positions" not in ctx
    assert "active_application" in ctx


@pytest.mark.asyncio
async def test_polymarket_first_light_context_has_finance(monkeypatch, db):
    monkeypatch.setattr("littleman.config.settings.active_application", "Polymarket trading")
    app = get_active_application()
    assert app is not None
    assert app.name == "Polymarket trading"
    ctx = await app.first_light_context()
    assert "wallet_balance_usdc" in ctx
    assert "budget_usdc" in ctx
