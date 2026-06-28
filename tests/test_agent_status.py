import pytest

from littleman.api.routes.agent import status
from littleman.meta.world_model import WorldModelManager


@pytest.mark.asyncio
async def test_agent_status_reports_simulated_balance_from_world_model(db):
    payload = await status(db)
    assert payload["balance_is_simulated"] is True


@pytest.mark.asyncio
async def test_agent_status_reports_reconciled_balance_from_world_model(db):
    wm = WorldModelManager(db)
    state = await wm.load()
    state.wallet_reconciled = True
    await wm.save(state)

    payload = await status(db)
    assert payload["balance_is_simulated"] is False
