import pytest


@pytest.fixture(autouse=True)
def isolate_fixture_api(request, monkeypatch):
    """Original foundation tests intentionally exercise opt-in fixture routes."""
    legacy = request.module.__name__.split(".")[-1] in {"test_offer_lifecycle", "test_agent_orchestration", "test_demo_negotiation", "test_procurement_agent", "test_llm_configuration", "test_llm_extractor", "test_llm_retry"}
    monkeypatch.setenv("PAYPOOL_ENABLE_LEGACY_API", "true" if legacy else "false")
    monkeypatch.setenv("PAYPOOL_PAYMENT_PROVIDER", "demo")
    monkeypatch.setenv("PAYPOOL_LLM_PROVIDER", "deterministic")
    monkeypatch.setenv("PAYPOOL_AGENT_NARRATOR_PROVIDER", "deterministic")
    monkeypatch.setenv("PAYPOOL_DEMO_NEGOTIATION_PROVIDER", "deterministic")
