import pytest


@pytest.mark.asyncio
async def test_first_light_uses_application_context(db, monkeypatch):
    monkeypatch.setattr("littleman.config.settings.active_application", "littleman.platform")
    monkeypatch.setattr(
        "littleman.llm.runtime.active",
        lambda: {"mode": "fake", "primary_model": "fake", "secondary_model": "fake"},
    )
    from littleman.meta.first_light import run

    result = await run(db)
    assert result["first_light"] == "complete"
    assert result["mode"] == "fake"
    # The bootstrap directive should not contain financial context in platform mode.
    assert "USDC" not in result["bootstrap_directive"].get("financial_context", "")


@pytest.mark.asyncio
async def test_first_light_polymarket_includes_financial_context(db, monkeypatch):
    monkeypatch.setattr("littleman.config.settings.active_application", "Polymarket trading")
    monkeypatch.setattr(
        "littleman.llm.runtime.active",
        lambda: {"mode": "fake", "primary_model": "fake", "secondary_model": "fake"},
    )
    from littleman.meta.first_light import run

    result = await run(db)
    assert result["first_light"] == "complete"
    assert result["mode"] == "fake"
    # Polymarket mode should surface the configured trading budget.
    assert "USDC" in result["bootstrap_directive"].get("financial_context", "")
