import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(autouse=True)
def use_deterministic_fixture(monkeypatch):
    monkeypatch.setenv("PAYPOOL_DEMO_NEGOTIATION_PROVIDER", "deterministic")


def test_demo_profiles_expose_one_buyer_and_one_seller() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/demo/profiles")

    assert response.status_code == 200
    profiles = response.json()
    assert [profile["role"] for profile in profiles] == ["RETAILER", "SELLER"]


def test_demo_agents_negotiate_a_ceiling_compliant_offer() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/demo/negotiations/run", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["offer"]["state"] == "SUBMITTED"
    assert body["ai_provider"] == "deterministic-test-fixture"
    assert body["offer"]["validation"]["status"] == "PENDING_AUTHORITATIVE_QUOTE"
    assert body["buyer_approval"] == "PENDING"
    assert body["seller_approval"] == "PENDING"
    assert len(body["messages"]) == 3


def test_demo_negotiation_stops_for_missing_constraints() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/demo/negotiations/run", json={"message": "I need rice"})

    assert response.status_code == 200
    assert response.json()["offer"] is None
    assert response.json()["buyer_approval"] == "NOT_READY"
