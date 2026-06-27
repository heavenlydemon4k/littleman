from littleman.llm import prompts


def test_chat_suggestions_do_not_assume_trading():
    assert "prediction-market trading agent" not in prompts.CHAT_SUGGESTIONS_SYSTEM


def test_calendar_maintenance_is_domain_agnostic():
    assert "open positions" not in prompts.CALENDAR_MAINTAIN_SYSTEM.lower()
    assert "watched market" not in prompts.CALENDAR_MAINTAIN_SYSTEM.lower()


def test_self_maintenance_is_domain_agnostic():
    assert "market," not in prompts.SELF_MAINTAIN_SYSTEM.lower()


def test_hypotheses_example_is_domain_agnostic():
    assert "BTC" not in prompts.HYPOTHESES_MAINTAIN_SYSTEM
    assert "Coinbase" not in prompts.HYPOTHESES_MAINTAIN_SYSTEM


def test_calendar_examples_are_domain_agnostic():
    assert "BTC" not in prompts.CALENDAR_MAINTAIN_SYSTEM
    assert "FOMC" not in prompts.CALENDAR_MAINTAIN_SYSTEM
    assert "position resolves" not in prompts.CALENDAR_MAINTAIN_SYSTEM.lower()


def test_workspace_core_exposure_is_domain_agnostic():
    assert "balances" not in prompts.WORKSPACE_CORE.lower() or "application-state snapshot" in prompts.WORKSPACE_CORE.lower()
    assert "open exposure" not in prompts.WORKSPACE_CORE.lower() or "application-state snapshot" in prompts.WORKSPACE_CORE.lower()
