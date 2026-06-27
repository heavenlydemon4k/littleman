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


def test_load_application_returns_platform_by_default():
    app = get_active_application()
    assert app is not None
    assert app.name == "littleman.platform"
