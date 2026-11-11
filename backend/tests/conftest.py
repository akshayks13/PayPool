import pytest


@pytest.fixture(autouse=True)
def isolate_fixture_api(request, monkeypatch):
    """Original foundation tests intentionally exercise opt-in fixture routes."""
    legacy = not request.module.__name__.endswith("test_commerce")
    monkeypatch.setenv("PAYPOOL_ENABLE_LEGACY_API", "true" if legacy else "false")
    monkeypatch.setenv("PAYPOOL_PAYMENT_PROVIDER", "demo")
    monkeypatch.setenv("PAYPOOL_LLM_PROVIDER", "deterministic")
    monkeypatch.setenv("PAYPOOL_AGENT_NARRATOR_PROVIDER", "deterministic")
    monkeypatch.setenv("PAYPOOL_DEMO_NEGOTIATION_PROVIDER", "deterministic")
