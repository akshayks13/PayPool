from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from fractions import Fraction

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.platform.clearing import apportion, inside
from app.platform.payments import PaymentError, Payments
from app.platform.seed import DEMO_PASSWORD


@pytest.fixture
def app(tmp_path):
    return create_app(f"sqlite:///{tmp_path / 'commerce.db'}", demo=True)


def login(app, name):
    client = TestClient(app)
    email = {"a": "ananya", "b": "rahul", "c": "meera"}.get(
        name, name
    ) + "@paypool.demo"
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    return client


def buy(client, ceiling=170, quantity=30, days=1):
    response = client.post(
        "/api/v1/procurement/requests",
        json={
            "product_id": "rice-sona",
            "zone_id": "south-zone",
            "dispatch_date": str(date.today() + timedelta(days=days)),
            "quantity_min": quantity,
            "quantity_max": quantity,
            "ceiling_minor": ceiling,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def cleared(app, ceiling=170):
    buyers = [login(app, n) for n in ["a", "b", "c"]]
    requests = [buy(b, ceiling) for b in buyers]
    seller = login(app, "seller")
    pool = seller.post(f"/api/v1/pools/{requests[0]['pool_id']}/clear").json()
    assert pool["status"] == "CLEARED", pool
    return buyers, requests, seller, pool


def authorize(buyer, pool):
    order = buyer.post(
        f"/api/v1/pools/{pool['id']}/approve", json={"version": pool["version"]}
    ).json()
    assert order["payment_status"] == "NOT_STARTED", order
    assert (
        buyer.post(f"/api/v1/orders/{order['id']}/checkout").json()["payment_status"]
        == "CREATED"
    )
    result = buyer.post(f"/api/v1/orders/{order['id']}/authorize")
    assert result.status_code == 200, result.text
    assert result.json()["payment_status"] == "AUTHORIZED"
    return result.json()


def test_anonymous_and_cross_role_mutations_are_rejected(app):
    anon = TestClient(app)
    assert anon.get("/api/v1/workspace").status_code == 401
    buyer = login(app, "a")
    assert (
        buyer.post(
            "/api/v1/admin/users/buyer-a/roles", json={"role": "ADMIN"}
        ).status_code
        == 403
    )
    assert (
        buyer.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "wrong"}).status_code
        == 403
    )
    assert (
        buyer.post(
            "/api/v1/auth/logout", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        TestClient(app)
        .post(
            "/api/v1/auth/login",
            json={"email": "ananya@paypool.demo", "password": "wrong"},
        )
        .status_code
        == 401
    )


def test_full_three_buyer_delivery_and_receipt_flow(app):
    buyers, requests, seller, pool = cleared(app)
    assert sum(a["freight_minor"] for a in pool["allocations"]) == 900
    assert all(a["total_minor"] == 4800 for a in pool["allocations"])
    orders = [authorize(b, pool) for b in buyers]
    assert seller.post(f"/api/v1/orders/{orders[0]['id']}/capture").status_code == 409
    dispatch = seller.post(
        f"/api/v1/pools/{pool['id']}/dispatch", json={"driver_id": "driver-demo"}
    )
    assert dispatch.status_code == 200, dispatch.text
    driver = login(app, "driver")
    for order in orders:
        payload = {
            "delivered_quantity": 30,
            "recipient_name": "Shop owner",
            "acknowledgement": True,
        }
        delivered = driver.post(f"/api/v1/orders/{order['id']}/pod", json=payload)
        assert delivered.status_code == 200, delivered.text
        assert delivered.json()["payment_status"] == "CAPTURED"
        assert driver.post(
            f"/api/v1/orders/{order['id']}/pod", json=payload
        ).status_code in {200, 403}
    receipt = buyers[0].get(f"/api/v1/orders/{orders[0]['id']}/receipt").json()
    assert receipt["status"] == "MATCHED"
    workspace = seller.get("/api/v1/workspace").json()
    assert workspace["pools"][0]["status"] == "COMPLETED"
    assert (
        next(p for p in workspace["products"] if p["id"] == "rice-sona")["stock"] == 410
    )


def test_dropout_voids_old_commitments_and_invalidates_old_approvals(app):
    buyers, requests, seller, pool = cleared(app)
    old_orders = [authorize(b, pool) for b in buyers]
    new = seller.post(
        f"/api/v1/pools/{pool['id']}/replan?exclude_request_id={requests[2]['id']}"
    )
    assert new.status_code == 200, new.text
    revised = new.json()
    assert revised["status"] == "CLEARED"
    assert len(revised["allocations"]) == 2
    assert revised["agreement_hash"] != pool["agreement_hash"]
    assert sorted(a["total_minor"] for a in revised["allocations"]) == [4900, 4900]
    for b, o in zip(buyers, old_orders):
        assert (
            b.get("/api/v1/workspace").json()["orders"][0]["payment_status"] == "VOIDED"
        )
        assert b.post(f"/api/v1/orders/{o['id']}/checkout").status_code == 409
    assert (
        buyers[0]
        .post(f"/api/v1/pools/{pool['id']}/approve", json={"version": pool["version"]})
        .status_code
        == 409
    )
    assert (
        seller.post(
            f"/api/v1/pools/{revised['id']}/dispatch", json={"driver_id": "driver-demo"}
        ).status_code
        == 409
    )


def test_tight_ceiling_becomes_infeasible_after_dropout(app):
    buyers, requests, seller, pool = cleared(app, ceiling=160)
    response = seller.post(
        f"/api/v1/pools/{pool['id']}/replan?exclude_request_id={requests[2]['id']}"
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "FAILED"
    assert response.json()["allocations"] == []


def test_cross_tenant_order_and_pool_visibility(app):
    buyers, requests, seller, pool = cleared(app)
    order = authorize(buyers[0], pool)
    assert buyers[1].get(f"/api/v1/orders/{order['id']}/receipt").status_code == 403
    assert buyers[1].post(f"/api/v1/orders/{order['id']}/authorize").status_code == 403
    visible = buyers[1].get("/api/v1/workspace").json()
    assert visible["orders"] == []
    assert all(
        a["buyer_id"] == "buyer-b" for p in visible["pools"] for a in p["allocations"]
    )
    assert not any(p["id"] == "buyer-a" for p in visible["people"])


def test_reserved_stock_cannot_be_edited_or_double_allocated(app):
    buyers, requests, seller, pool = cleared(app)
    item = next(
        p
        for p in seller.get("/api/v1/workspace").json()["products"]
        if p["id"] == "rice-sona"
    )
    payload = {
        k: item[k]
        for k in [
            "title",
            "unit",
            "currency",
            "stock",
            "weight_grams",
            "volume_cm3",
            "attributes",
            "tiers",
        ]
    }
    assert (
        seller.put("/api/v1/seller/products/rice-sona", json=payload).status_code == 409
    )
    assert item["available_stock"] == 410


def test_delivery_exception_does_not_capture(app):
    buyers, requests, seller, pool = cleared(app)
    orders = [authorize(b, pool) for b in buyers]
    seller.post(
        f"/api/v1/pools/{pool['id']}/dispatch", json={"driver_id": "driver-demo"}
    )
    driver = login(app, "driver")
    result = driver.post(
        f"/api/v1/orders/{orders[0]['id']}/pod",
        json={
            "delivered_quantity": 20,
            "recipient_name": "Shop owner",
            "acknowledgement": True,
            "exception": "MISSING_ITEMS",
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["payment_status"] == "AUTHORIZED"
    assert result.json()["status"] == "DELIVERY_EXCEPTION"
    assert seller.post(f"/api/v1/orders/{orders[0]['id']}/capture").status_code == 409


def test_freight_rounding_conserves_every_cent():
    for total in range(1, 50):
        shares = apportion(
            total, [Fraction(1), Fraction(2), Fraction(3)], ["a", "b", "c"]
        )
        assert sum(shares) == total
        assert all(v >= 0 for v in shares)
    assert inside([0, 0], [[0, 0], [1, 0], [1, 1], [0, 1]])
    assert not inside([2, 2], [[0, 0], [1, 0], [1, 1], [0, 1]])


def test_impossible_route_and_unapproved_substitute_are_rejected(app):
    a = login(app, "a")
    payload = {
        "product_id": "rice-sona",
        "zone_id": "south-zone",
        "dispatch_date": "2099-01-01",
        "quantity_min": 30,
        "quantity_max": 30,
        "ceiling_minor": 170,
        "substitute_product_ids": ["rice-basmati"],
    }
    assert a.post("/api/v1/procurement/requests", json=payload).status_code == 422
    record = buy(a)
    seller = login(app, "seller")
    assert (
        seller.post(f"/api/v1/pools/{record['pool_id']}/clear").json()["status"]
        == "FAILED"
    )


def test_refunds_are_idempotent_and_cannot_exceed_capture(app):
    buyers, requests, seller, pool = cleared(app)
    orders = [authorize(b, pool) for b in buyers]
    seller.post(
        f"/api/v1/pools/{pool['id']}/dispatch", json={"driver_id": "driver-demo"}
    )
    driver = login(app, "driver")
    order = orders[0]
    driver.post(
        f"/api/v1/orders/{order['id']}/pod",
        json={
            "delivered_quantity": 30,
            "recipient_name": "Shop owner",
            "acknowledgement": True,
        },
    )
    path = f"/api/v1/orders/{order['id']}/refund"
    headers = {"Idempotency-Key": "test-refund-operation-1"}
    first = seller.post(
        path, json={"amount_minor": 1000, "reason": "Two bags damaged"}, headers=headers
    )
    assert first.status_code == 200, first.text
    second = seller.post(
        path, json={"amount_minor": 1000, "reason": "Two bags damaged"}, headers=headers
    )
    assert second.json() == first.json()
    assert (
        seller.post(
            path,
            json={"amount_minor": 2000, "reason": "Different terms"},
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        seller.post(
            path,
            json={"amount_minor": 4800, "reason": "Too large"},
            headers={"Idempotency-Key": "another-operation"},
        ).status_code
        == 409
    )
    assert (
        buyers[0].get("/api/v1/workspace").json()["orders"][0]["refunded_minor"] == 1000
    )


def test_catalog_import_requires_review_and_is_atomic(app):
    seller = login(app, "seller")
    preview = seller.post(
        "/api/v1/seller/imports/preview",
        files={
            "file": (
                "products.csv",
                b"product_name,price,stock,unit,currency\nFlour,2.50,100,kg,USD\nBad,wrong,3,kg,USD\n",
                "text/csv",
            )
        },
    )
    assert preview.status_code == 200, preview.text
    batch = preview.json()
    assert len(batch["products"]) == 1 and len(batch["errors"]) == 1
    assert len(seller.get("/api/v1/workspace").json()["products"]) == 3
    assert (
        seller.post(f"/api/v1/seller/imports/{batch['id']}/commit").status_code == 200
    )
    seller.post(f"/api/v1/seller/imports/{batch['id']}/commit")
    assert len(seller.get("/api/v1/workspace").json()["products"]) == 4


def test_discovery_uses_persisted_stock_tiers_and_demand(app):
    buyer = login(app, "a")
    response = buyer.post(
        "/api/v1/procurement/discover",
        json={
            "message": "30 kg Sona Masoori rice by 2099-01-01, landed price below USD 1.70/kg.",
            "currency": "USD",
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["engine"] == "deterministic"
    assert result["agent_trace"]["buyer"]["tools"] == [
        {"name": "search_catalog", "outcome": "completed"}
    ]
    assert len(result["agent_trace"]["distributor"]) == 2
    assert result["candidates"]
    assert all("Sona Masoori" in c["title"] for c in result["candidates"])
    assert all(c["requires_final_clearing"] for c in result["candidates"])
    assert buyer.get("/api/v1/workspace").json()["requests"] == []


def test_session_survives_app_restart(tmp_path):
    url = f"sqlite:///{tmp_path / 'persistent.db'}"
    first = create_app(url, demo=True)
    a = login(first, "a")
    record = buy(a)
    second = TestClient(create_app(url, demo=True))
    second.cookies.update(a.cookies)
    assert second.get("/api/v1/me").status_code == 200
    assert second.get("/api/v1/workspace").json()["requests"][0]["id"] == record["id"]


def test_payment_timeout_records_uncertainty_and_blocks_dispatch(app, monkeypatch):
    buyers, requests, seller, pool = cleared(app)
    order = (
        buyers[0]
        .post(f"/api/v1/pools/{pool['id']}/approve", json={"version": pool["version"]})
        .json()
    )

    def uncertain(*args):
        raise PaymentError("Response uncertain")

    monkeypatch.setattr(app.state.payments, "create", uncertain)
    result = buyers[0].post(f"/api/v1/orders/{order['id']}/checkout").json()
    assert result["payment_status"] == "REQUIRES_RECONCILIATION"
    assert (
        seller.post(
            f"/api/v1/pools/{pool['id']}/dispatch", json={"driver_id": "driver-demo"}
        ).status_code
        == 409
    )
    assert (
        buyers[0].get("/api/v1/workspace").json()["orders"][0]["payment_status"]
        == "REQUIRES_RECONCILIATION"
    )


def test_webhook_rejects_unsigned_payload_in_demo(app):
    response = TestClient(app).post(
        "/api/v1/webhooks/paypal",
        json={"id": "fake", "event_type": "PAYMENT.CAPTURE.COMPLETED"},
    )
    assert response.status_code == 400


def test_legacy_fixture_routes_disabled_by_default(app):
    assert TestClient(app).get("/api/v1/demo/profiles").status_code == 404


def test_paypal_adapter_uses_server_amount_and_stable_idempotency(monkeypatch):
    monkeypatch.setenv("PAYPOOL_PAYMENT_PROVIDER", "paypal_sandbox")
    payments = Payments(demo=True)
    monkeypatch.setattr(payments, "token", lambda: "test-only-token")
    calls = []

    def fake(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return httpx.Response(
            201,
            json={"id": "SANDBOX-ORDER", "links": []},
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(httpx, "request", fake)
    order = {"id": "order-1", "currency": "USD", "total_minor": 4901}
    payments.create(order)
    payments.create(order)
    assert (
        calls[0][2]["headers"]["PayPal-Request-Id"]
        == calls[1][2]["headers"]["PayPal-Request-Id"]
    )
    assert calls[0][2]["json"]["purchase_units"][0]["amount"]["value"] == "49.01"
    assert calls[0][1].startswith("https://api-m.sandbox.paypal.com/")


def test_replan_retries_return_the_same_replacement(app):
    _, requests, seller, pool = cleared(app)
    path = f"/api/v1/pools/{pool['id']}/replan?exclude_request_id={requests[2]['id']}"
    first = seller.post(path)
    assert first.status_code == 200, first.text
    assert seller.post(path).json()["id"] == first.json()["id"]
    assert len(seller.get("/api/v1/workspace").json()["pools"]) == 2
    assert seller.post(f"/api/v1/pools/{pool['id']}/replan").status_code == 409


def test_demo_accounts_and_sessions_are_blocked_when_demo_disabled(
    tmp_path, monkeypatch
):
    url = f"sqlite:///{tmp_path / 'demo-switch.db'}"
    demo = create_app(url, demo=True)
    buyer = login(demo, "a")
    monkeypatch.setenv("PAYPOOL_PAYMENT_PROVIDER", "paypal_sandbox")
    real = TestClient(create_app(url, demo=False))
    real.cookies.update(buyer.cookies)
    assert real.get("/api/v1/me").status_code == 401
    assert (
        real.post(
            "/api/v1/auth/login",
            json={"email": "ananya@paypool.demo", "password": DEMO_PASSWORD},
        ).status_code
        == 401
    )
    assert real.get("/api/v1/config").json()["accounts"] == []


def test_invalid_delivery_polygons_are_rejected(app):
    seller = login(app, "seller")
    for polygon in ([[0, 0], [1, 1], [1, 0], [0, 1]], [[0, 0], [1, 1], [2, 2]]):
        response = seller.post(
            "/api/v1/seller/zones",
            json={
                "name": "Bad polygon",
                "polygon": polygon,
                "depot": [0, 0],
                "base_freight_minor": 0,
                "stop_fee_minor": 0,
            },
        )
        assert response.status_code == 422


def test_notification_receipts_are_owner_scoped(app):
    buyer, other = login(app, "a"), login(app, "b")
    buy(buyer)
    notification = buyer.get("/api/v1/workspace").json()["notifications"][0]
    path = f"/api/v1/notifications/{notification['id']}/read"
    assert other.post(path).status_code == 403
    assert buyer.post(path).json()["read"] is True


def test_verified_webhooks_deduplicate_and_use_current_provider_state(app, monkeypatch):
    buyers, _, _, pool = cleared(app)
    order = authorize(buyers[0], pool)
    provider = app.state.payments
    monkeypatch.setattr(provider, "mode", "paypal_sandbox")
    monkeypatch.setattr(provider, "verify_webhook", lambda headers, event: None)
    calls = []

    def read(method, path, **kwargs):
        calls.append(path)
        assert method == "GET"
        return {
            "id": order["provider_order_id"],
            "status": "COMPLETED",
            "purchase_units": [
                {
                    "amount": {"currency_code": "USD", "value": "48.00"},
                    "payments": {
                        "captures": [{"id": "TRUSTED-CAPTURE", "status": "COMPLETED"}]
                    },
                }
            ],
        }

    monkeypatch.setattr(provider, "call", read)
    event = {
        "id": "EVENT-1",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "TRUSTED-CAPTURE",
            "supplementary_data": {
                "related_ids": {"order_id": order["provider_order_id"]}
            },
        },
    }
    client = TestClient(app)
    assert client.post("/api/v1/webhooks/paypal", json=event).status_code == 200
    assert client.post("/api/v1/webhooks/paypal", json=event).json() == {
        "duplicate": True
    }
    assert len(calls) == 1
    event.update(id="EVENT-2", event_type="PAYMENT.CAPTURE.DENIED")
    assert client.post("/api/v1/webhooks/paypal", json=event).status_code == 200
    visible = buyers[0].get("/api/v1/workspace").json()["orders"][0]
    assert visible["payment_status"] == "CAPTURED"
    assert visible["capture_id"] == "TRUSTED-CAPTURE"
    assert (
        buyers[0].get(f"/api/v1/orders/{order['id']}/receipt").json()["status"]
        == "PENDING"
    )


def test_dispatch_rechecks_external_authorization_expiry(app, monkeypatch):
    buyers, _, seller, pool = cleared(app)
    orders = [authorize(b, pool) for b in buyers]
    provider = app.state.payments
    monkeypatch.setattr(provider, "mode", "paypal_sandbox")

    def read(method, path, **kwargs):
        if path.startswith("/v2/checkout/orders/"):
            order = next(o for o in orders if path.endswith(o["provider_order_id"]))
            return {
                "purchase_units": [
                    {
                        "amount": {"currency_code": "USD", "value": "48.00"},
                        "payments": {
                            "authorizations": [{"id": order["authorization_id"]}]
                        },
                    }
                ]
            }
        return {"id": path.split("/")[-1], "status": "EXPIRED"}

    monkeypatch.setattr(provider, "call", read)
    response = seller.post(
        f"/api/v1/pools/{pool['id']}/dispatch", json={"driver_id": "driver-demo"}
    )
    assert response.status_code == 409
    workspace = seller.get("/api/v1/workspace").json()
    assert workspace["pools"][0]["status"] == "CLEARED"
    assert all(o["payment_status"] == "EXPIRED" for o in workspace["orders"])


def test_catalog_specification_changes_require_new_buyer_consent(app):
    buyers = [login(app, n) for n in ("a", "b", "c")]
    requests = [buy(b) for b in buyers]
    seller = login(app, "seller")
    item = next(
        p
        for p in seller.get("/api/v1/workspace").json()["products"]
        if p["id"] == "rice-sona"
    )
    payload = {
        k: item[k]
        for k in (
            "title",
            "unit",
            "currency",
            "stock",
            "weight_grams",
            "volume_cm3",
            "attributes",
            "tiers",
        )
    }
    payload["attributes"] = {"variety": "Basmati", "brand": "Harvest"}
    assert (
        seller.put("/api/v1/seller/products/rice-sona", json=payload).status_code == 200
    )
    response = seller.post(f"/api/v1/pools/{requests[0]['pool_id']}/clear")
    assert response.status_code == 409
    assert "specifications changed" in response.json()["detail"]


def test_concurrent_workers_cannot_reserve_the_same_inventory_twice(app):
    with app.state.store.transaction() as tx:
        product = tx.get("products", "rice-sona")
        product["stock"] = 100
        tx.put("products", product)
    buyers = [login(app, n) for n in ("a", "b", "c")]
    first = [buy(b, days=1) for b in buyers]
    second = [buy(b, days=2) for b in buyers]
    # Independent app instances have different in-process locks and engines.
    # SQLite's transaction lock must still protect the shared inventory.
    other_app = create_app(str(app.state.store.engine.url), demo=True)
    sellers = [login(app, "seller"), login(other_app, "seller")]
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [
            workers.submit(seller.post, f"/api/v1/pools/{requests[0]['pool_id']}/clear")
            for seller, requests in zip(sellers, (first, second))
        ]
        responses = [future.result() for future in futures]
    assert all(r.status_code == 200 for r in responses)
    assert sorted(r.json()["status"] for r in responses) == ["CLEARED", "FAILED"]
    product = next(
        p
        for p in sellers[0].get("/api/v1/workspace").json()["products"]
        if p["id"] == "rice-sona"
    )
    assert product["stock"] == 100
    assert product["available_stock"] == 10
