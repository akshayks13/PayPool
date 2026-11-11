from test_commerce import app as app
from test_commerce import buy, login
from test_extended import offer_payload


def test_saved_conversation_is_private_versioned_and_contains_no_stale_quotes(app):
    buyer, other = login(app, "a"), login(app, "b")
    assert buyer.get("/api/v1/procurement/conversation").json()["version"] == 0
    payload = {
        "message": "I need 30 kg Sona Masoori rice",
        "currency": "USD",
        "conversation_version": 0,
    }
    result = buyer.post("/api/v1/procurement/discover", json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["conversation"]["version"] == 1
    saved = login(app, "a").get("/api/v1/procurement/conversation").json()
    assert saved["message"] == payload["message"]
    assert saved["intent"]["quantity"] == "30"
    assert "candidates" not in saved and len(saved["history"]) == 1
    assert other.get("/api/v1/procurement/conversation").json()["message"] == ""
    # A stale device cannot overwrite the other device's task.
    assert buyer.post("/api/v1/procurement/discover", json=payload).status_code == 409
    assert (
        buyer.post(
            "/api/v1/procurement/conversation/reset", json={"version": 0}
        ).status_code
        == 409
    )
    assert (
        buyer.post(
            "/api/v1/procurement/conversation/reset", json={"version": 1}
        ).json()["version"]
        == 2
    )
    assert buyer.get("/api/v1/procurement/conversation").json()["intent"] is None
    assert buyer.get("/api/v1/workspace").json()["requests"] == []
    assert (
        login(app, "seller").get("/api/v1/procurement/conversation").status_code == 403
    )


def test_inflight_model_response_cannot_overwrite_newer_conversation(app, monkeypatch):
    from app.modules.negotiation import procurement_router
    from app.modules.negotiation.procurement_parser import (
        DeterministicProcurementParser,
    )

    class ConcurrentParser:
        def parse(self, request):
            with app.state.store.transaction() as tx:
                tx.put(
                    "procurement_conversations",
                    {
                        "id": "buyer-a",
                        "version": 1,
                        "message": "Another device reset this task",
                        "intent": None,
                        "history": [],
                    },
                )
            return DeterministicProcurementParser().parse(request)

    monkeypatch.setattr(
        procurement_router, "get_procurement_parser", lambda: ConcurrentParser()
    )
    buyer = login(app, "a")
    response = buyer.post(
        "/api/v1/procurement/discover",
        json={
            "message": "30 kg rice",
            "currency": "USD",
            "conversation_version": 0,
        },
    )
    assert response.status_code == 409
    assert (
        buyer.get("/api/v1/procurement/conversation").json()["message"]
        == "Another device reset this task"
    )


def test_discovery_and_catalog_exclude_unavailable_merchant_and_archived_products(app):
    buyer = login(app, "a")
    payload = {
        "message": "30 kg Sona Masoori rice by 2099-01-01, landed price below USD 1.70/kg",
        "currency": "USD",
    }
    with app.state.store.transaction() as tx:
        item = tx.get("products", "rice-sona")
        item["active"] = False
        tx.put("products", item)
    candidates = buyer.post("/api/v1/procurement/discover", json=payload).json()[
        "candidates"
    ]
    assert {c["product_id"] for c in candidates} == {"rice-sona-alt"}
    with app.state.store.transaction() as tx:
        seller = tx.get("users", "seller-demo")
        seller["verified"] = False
        tx.put("users", seller)
    assert (
        buyer.post("/api/v1/procurement/discover", json=payload).json()["candidates"]
        == []
    )
    assert buyer.get("/api/v1/catalog/search").json()["total"] == 0


def test_catalog_facets_and_page_boundaries_use_authoritative_stock(app):
    buyer = login(app, "a")
    first = buyer.get(
        "/api/v1/catalog/search", params={"brand": "harvest", "unit": "kg", "limit": 1}
    ).json()
    second = buyer.get(
        "/api/v1/catalog/search",
        params={"brand": "HARVEST", "unit": "kg", "limit": 1, "offset": 1},
    ).json()
    assert first["total"] == second["total"] == 2
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert buyer.get("/api/v1/catalog/search?unit=box").json()["total"] == 0
    with app.state.store.transaction() as tx:
        item = tx.get("products", "rice-sona-alt")
        item["stock"] = 0
        tx.put("products", item)
    assert buyer.get("/api/v1/catalog/search?brand=Field").json()["total"] == 0
    assert (
        buyer.get("/api/v1/catalog/search?brand=Field&in_stock=false").json()["total"]
        == 1
    )


def test_audit_pagination_can_reach_old_history_without_cross_tenant_leaks(app):
    a, b, admin = login(app, "a"), login(app, "b"), login(app, "admin")
    with app.state.store.transaction() as tx:
        for i in range(125):
            tx.put(
                "audit",
                {
                    "id": f"history-{i:03}",
                    "at": "2026-11-11T00:00:00+00:00",
                    "actor": "buyer-a",
                    "action": "TEST_HISTORY",
                    "subject": f"own-{i}",
                    "details": {},
                },
            )
    last = a.get("/api/v1/audit?q=TEST_HISTORY&offset=120&limit=20").json()
    assert last["total"] == 125 and len(last["items"]) == 5
    first = a.get("/api/v1/audit?q=TEST_HISTORY&limit=20").json()
    assert not {e["id"] for e in first["items"]}.intersection(
        e["id"] for e in last["items"]
    )
    assert b.get("/api/v1/audit?q=TEST_HISTORY").json()["total"] == 0
    assert admin.get("/api/v1/audit?q=TEST_HISTORY").json()["total"] == 125
    assert a.get("/api/v1/audit?q=%25").json()["total"] == 0
    assert a.get("/api/v1/audit?limit=101").status_code == 422


def test_reject_is_counterparty_only_versioned_and_does_not_create_an_order(app):
    buyer, seller = login(app, "a"), login(app, "seller")
    buying = buy(buyer)
    offer = seller.post(
        "/api/v1/offers",
        json=offer_payload(buying["id"]),
        headers={"Idempotency-Key": "rejectable-proposal"},
    ).json()
    path = f"/api/v1/offers/{offer['id']}/reject"
    assert seller.post(path, json={"version": 1}).status_code == 403
    assert buyer.post(path, json={"version": 2}).status_code == 409
    assert buyer.post(path, json={"version": 1}).json()["status"] == "REJECTED"
    assert buyer.post(path, json={"version": 1}).json()["status"] == "REJECTED"
    assert (
        buyer.post(
            f"/api/v1/offers/{offer['id']}/accept", json={"version": 1}
        ).status_code
        == 409
    )
    assert buyer.get("/api/v1/workspace").json()["orders"] == []


def test_revoked_roles_cannot_continue_existing_negotiations(app):
    buyer, seller, admin = login(app, "a"), login(app, "seller"), login(app, "admin")
    buying = buy(buyer)
    offer = seller.post(
        "/api/v1/offers",
        json=offer_payload(buying["id"]),
        headers={"Idempotency-Key": "revoked-proposal"},
    ).json()
    assert (
        admin.post(
            "/api/v1/admin/users/buyer-a/roles/revoke", json={"role": "RETAILER"}
        ).status_code
        == 200
    )
    for action in ("accept", "reject"):
        assert (
            buyer.post(
                f"/api/v1/offers/{offer['id']}/{action}", json={"version": 1}
            ).status_code
            == 403
        )
