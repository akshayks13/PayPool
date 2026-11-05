from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


def offer_payload() -> dict[str, object]:
    return {
        "procurement_request_id": str(uuid4()),
        "buyer_id": str(uuid4()),
        "seller_id": str(uuid4()),
        "actor_id": str(uuid4()),
        "price_ceiling_per_unit_minor": 5200,
        "terms": {
            "sku_id": "rice-sona-masoori-25kg",
            "quantity_min": 1,
            "quantity_max": 4,
            "unit_price_minor": 4600,
            "estimated_freight_per_unit_minor": 500,
            "currency": "inr",
            "delivery_terms": "Friday delivery",
            "substitution_consent": False,
        },
    }


def test_create_offer_marks_estimate_pending_authoritative_quote() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/offers", json=offer_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "SUBMITTED"
    assert body["version"] == 1
    assert body["terms"]["currency"] == "INR"
    assert body["validation"]["status"] == "PENDING_AUTHORITATIVE_QUOTE"


def test_offer_above_ceiling_is_marked_failed() -> None:
    payload = offer_payload()
    payload["terms"]["estimated_freight_per_unit_minor"] = 700  # type: ignore[index]

    with TestClient(create_app()) as client:
        response = client.post("/api/v1/offers", json=payload)

    assert response.status_code == 201
    assert response.json()["validation"]["status"] == "FAILED"


def test_counter_versions_offer_and_acceptance_fails_closed_without_quote() -> None:
    payload = offer_payload()
    buyer_id = payload["buyer_id"]
    with TestClient(create_app()) as client:
        created = client.post("/api/v1/offers", json=payload).json()
        counter = client.post(
            f"/api/v1/offers/{created['id']}/counter",
            json={"actor_id": str(uuid4()), "terms": payload["terms"]},
        )
        accepted = client.post(
            f"/api/v1/offers/{created['id']}/accept",
            json={"actor_id": buyer_id},
        )

    assert counter.status_code == 200
    assert counter.json()["state"] == "COUNTERED"
    assert counter.json()["version"] == 2
    assert accepted.status_code == 409
    assert accepted.json()["detail"]["code"] == "AUTHORITATIVE_QUOTE_REQUIRED"
