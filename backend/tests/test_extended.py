import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Event

from fastapi.testclient import TestClient
from test_commerce import app as app
from test_commerce import authorize, buy, cleared, login

from app.platform import worker
from app.platform.acp import validate
from app.platform.payments import PaymentError
from app.platform.store import Store


def offer_payload(request_id, price=150):
    return {
        "request_id": request_id,
        "product_id": "rice-sona",
        "quantity_min": 30,
        "quantity_max": 30,
        "unit_price_minor": price,
        "expires_in_hours": 24,
        "note": "Review proposed terms",
    }


def test_persistent_negotiation_revalidates_and_flows_into_final_quote(app):
    buyers = [login(app, n) for n in ("a", "b", "c")]
    requests = [buy(b) for b in buyers]
    seller = login(app, "seller")
    payload = offer_payload(requests[0]["id"])
    headers = {"Idempotency-Key": "seller-proposal-1"}
    response = seller.post("/api/v1/offers", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    offer = response.json()
    assert (
        seller.post("/api/v1/offers", json=payload, headers=headers).json()["id"]
        == offer["id"]
    )
    assert (
        seller.post(
            f"/api/v1/offers/{offer['id']}/accept", json={"version": 1}
        ).status_code
        == 403
    )
    counter = {k: v for k, v in payload.items() if k != "request_id"}
    counter.update(unit_price_minor=145, version=1)
    revised = buyers[0].post(f"/api/v1/offers/{offer['id']}/counter", json=counter)
    assert revised.status_code == 200, revised.text
    assert revised.json()["version"] == 2
    assert (
        seller.post(
            f"/api/v1/offers/{offer['id']}/accept", json={"version": 1}
        ).status_code
        == 409
    )
    assert (
        seller.post(
            f"/api/v1/offers/{offer['id']}/accept", json={"version": 2}
        ).status_code
        == 200
    )
    final = seller.post(f"/api/v1/pools/{requests[0]['pool_id']}/clear").json()
    assert final["status"] == "CLEARED"
    allocation = next(a for a in final["allocations"] if a["buyer_id"] == "buyer-a")
    assert allocation["unit_price_minor"] == 145 and allocation["total_minor"] == 4650
    assert allocation["ceiling_minor"] == 170
    assert buyers[1].get(f"/api/v1/offers/{offer['id']}").status_code == 403
    assert len(buyers[0].get(f"/api/v1/offers/{offer['id']}").json()["revisions"]) == 2
    assert buyers[0].get("/api/v1/orders").json() == []


def test_buyer_bid_cannot_bypass_seller_floor_and_expired_offers(app):
    buyer, seller = login(app, "a"), login(app, "seller")
    request = buy(buyer)
    response = buyer.post(
        "/api/v1/offers",
        json=offer_payload(request["id"], 130),
        headers={"Idempotency-Key": "low-buyer-bid-1"},
    )
    assert response.status_code == 200, response.text
    offer = response.json()
    assert (
        seller.post(
            f"/api/v1/offers/{offer['id']}/accept", json={"version": 1}
        ).status_code
        == 422
    )
    with app.state.store.transaction() as tx:
        offer["expires_at"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        tx.put("offers", offer)
    assert (
        seller.post(
            f"/api/v1/offers/{offer['id']}/counter",
            json={
                **{
                    k: v
                    for k, v in offer_payload(request["id"]).items()
                    if k != "request_id"
                },
                "version": 1,
            },
        ).status_code
        == 409
    )


def test_integer_solver_finds_interior_quantities(app):
    with app.state.store.transaction() as tx:
        zone = tx.get("zones", "south-zone")
        zone.update(min_weight_grams=44000, max_weight_grams=44000)
        tx.put("zones", zone)
    for name in ("a", "b"):
        client = login(app, name)
        request = client.post(
            "/api/v1/procurement/requests",
            json={
                "product_id": "rice-sona",
                "zone_id": "south-zone",
                "dispatch_date": str(date.today() + timedelta(days=1)),
                "quantity_min": 21,
                "quantity_max": 24,
                "ceiling_minor": 300,
            },
        ).json()
    result = login(app, "seller").post(f"/api/v1/pools/{request['pool_id']}/clear")
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "CLEARED"
    assert sum(a["quantity"] for a in result.json()["allocations"]) == 44


def test_standing_orders_generate_only_requests_once_per_occurrence(app):
    buyer = login(app, "a")
    payload = {
        "name": "Weekly rice",
        "request": {
            "product_id": "rice-sona",
            "zone_id": "south-zone",
            "dispatch_date": str(date.today() + timedelta(days=1)),
            "quantity_min": 30,
            "quantity_max": 30,
            "ceiling_minor": 170,
        },
        "repeat_days": 7,
        "lookahead_days": 7,
    }
    result = buyer.post("/api/v1/standing-orders", json=payload)
    assert result.status_code == 200, result.text
    assert buyer.get("/api/v1/workspace").json()["requests"] == []
    worker.tick(app.state.store, app.state.payments)
    worker.tick(app.state.store, app.state.payments)
    workspace = buyer.get("/api/v1/workspace").json()
    assert len(workspace["requests"]) == 1
    assert workspace["orders"] == []
    assert len(buyer.get("/api/v1/features").json()["standing_orders"]) == 1


def test_cutoff_and_weekday_are_enforced_before_membership(app):
    buyer = login(app, "a")
    with app.state.store.transaction() as tx:
        zone = tx.get("zones", "south-zone")
        zone["cutoff_hours_before"] = 72
        tx.put("zones", zone)
    response = buyer.post(
        "/api/v1/procurement/requests",
        json={
            "product_id": "rice-sona",
            "zone_id": "south-zone",
            "dispatch_date": str(date.today() + timedelta(days=1)),
            "quantity_min": 30,
            "quantity_max": 30,
            "ceiling_minor": 170,
        },
    )
    assert response.status_code == 409
    assert buyer.get("/api/v1/workspace").json()["requests"] == []


def test_worker_dead_letter_retry_is_durable_and_owner_protected(app, monkeypatch):
    admin, buyer = login(app, "admin"), login(app, "a")
    with app.state.store.transaction() as tx:
        event = tx.audit("buyer-a", "TEST_PROJECTION", "unrelated")
    original = worker.process_event

    def fail(store, event_id):
        raise RuntimeError("Do not persist unsafe exception contents")

    monkeypatch.setattr(worker, "process_event", fail)
    result = worker.tick(app.state.store, app.state.payments)
    assert result["failed"] > 0
    assert buyer.post(f"/api/v1/admin/jobs/{event['id']}/retry").status_code == 403
    assert admin.post(f"/api/v1/admin/jobs/{event['id']}/retry").status_code == 200
    monkeypatch.setattr(worker, "process_event", original)
    assert admin.post("/api/v1/admin/worker/tick").status_code == 200
    with app.state.store.transaction() as tx:
        assert tx.get("outbox", event["id"])["status"] == "DELIVERED"
    assert not original(app.state.store, event["id"])


def test_recipient_confirmation_prevents_driver_only_capture(app):
    with app.state.store.transaction() as tx:
        zone = tx.get("zones", "south-zone")
        zone["recipient_confirmation_required"] = True
        tx.put("zones", zone)
    buyers, _, seller, pool = cleared(app)
    orders = [authorize(b, pool) for b in buyers]
    assert (
        seller.post(
            f"/api/v1/pools/{pool['id']}/dispatch",
            json={"driver_id": "driver-demo", "vehicle_id": "demo-van"},
        ).status_code
        == 200
    )
    assert (
        next(
            p
            for p in seller.get("/api/v1/workspace").json()["products"]
            if p["id"] == "rice-sona"
        )["stock"]
        == 410
    )
    driver = login(app, "driver")
    payload = {
        "delivered_quantity": 30,
        "recipient_name": "Shop recipient",
        "acknowledgement": True,
    }
    result = driver.post(f"/api/v1/orders/{orders[0]['id']}/pod", json=payload)
    assert result.json()["status"] == "AWAITING_CONFIRMATION"
    assert result.json()["payment_status"] == "AUTHORIZED"
    assert driver.post(f"/api/v1/orders/{orders[0]['id']}/capture").status_code == 409
    path = f"/api/v1/orders/{orders[0]['id']}/confirm-delivery"
    assert buyers[1].post(path).status_code == 403
    assert buyers[0].post(path).json()["payment_status"] == "CAPTURED"
    assert buyers[0].post(path).json()["payment_status"] == "CAPTURED"


def test_exception_redelivery_keeps_evidence_and_stock_is_not_debited_twice(app):
    buyers, _, seller, pool = cleared(app)
    orders = [authorize(b, pool) for b in buyers]
    seller.post(
        f"/api/v1/pools/{pool['id']}/dispatch", json={"driver_id": "driver-demo"}
    )
    driver = login(app, "driver")
    driver.post(
        f"/api/v1/orders/{orders[0]['id']}/pod",
        json={
            "delivered_quantity": 20,
            "recipient_name": "Shop recipient",
            "acknowledgement": True,
            "exception": "MISSING_ITEMS",
        },
    )
    path = f"/api/v1/orders/{orders[0]['id']}/resolve-exception"
    assert (
        buyers[0]
        .post(path, json={"action": "REDELIVER", "reason": "Deliver remaining bags"})
        .status_code
        == 403
    )
    result = seller.post(
        path, json={"action": "REDELIVER", "reason": "Deliver remaining bags"}
    )
    assert result.status_code == 200, result.text
    assert len(result.json()["pod_history"]) == 1
    final = driver.post(
        f"/api/v1/orders/{orders[0]['id']}/pod",
        json={
            "delivered_quantity": 30,
            "recipient_name": "Shop recipient",
            "acknowledgement": True,
        },
    )
    assert final.json()["payment_status"] == "CAPTURED"
    assert (
        next(
            p
            for p in seller.get("/api/v1/workspace").json()["products"]
            if p["id"] == "rice-sona"
        )["stock"]
        == 410
    )


def test_inventory_and_fleet_require_fresh_stock_and_capacity(app):
    seller = login(app, "seller")
    result = seller.post(
        "/api/v1/seller/inventory",
        json={
            "product_id": "rice-sona",
            "delta": 20,
            "expected_stock": 500,
            "reason": "New supplier stock",
        },
    )
    assert result.status_code == 200
    assert (
        seller.post(
            "/api/v1/seller/inventory",
            json={
                "product_id": "rice-sona",
                "delta": 20,
                "expected_stock": 500,
                "reason": "Replay stale balance",
            },
        ).status_code
        == 409
    )
    buyers, _, seller, pool = cleared(app)
    [authorize(b, pool) for b in buyers]
    small = seller.post(
        "/api/v1/seller/vehicles",
        json={
            "name": "Small van",
            "registration": "SMALL-01",
            "max_weight_grams": 50000,
            "max_volume_cm3": 400000,
        },
    ).json()
    assert (
        seller.post(
            f"/api/v1/pools/{pool['id']}/dispatch",
            json={"driver_id": "driver-demo", "vehicle_id": small["id"]},
        ).status_code
        == 409
    )
    assert (
        seller.post(
            f"/api/v1/pools/{pool['id']}/dispatch",
            json={"driver_id": "driver-demo", "vehicle_id": "demo-van"},
        ).status_code
        == 200
    )


def test_acp_is_pinned_idempotent_and_cannot_approve_or_pay(app, monkeypatch):
    assert TestClient(app).get("/acp/checkout_sessions/missing").status_code == 503
    buyers, _, _, pool = cleared(app)
    order = (
        buyers[0]
        .post(f"/api/v1/pools/{pool['id']}/approve", json={"version": pool["version"]})
        .json()
    )
    access = (
        buyers[0]
        .post("/api/v1/me/agent-access", json={"name": "Contract agent"})
        .json()
    )
    monkeypatch.setenv("ACP_ENABLED", "true")
    client = TestClient(
        app,
        headers={
            "Authorization": "Bearer " + access["token"],
            "API-Version": "2026-04-17",
            "Idempotency-Key": "create-session-1",
        },
    )
    payload = {
        "line_items": [{"id": "rice-sona"}],
        "currency": "usd",
        "capabilities": {},
        "quote_id": order["id"],
    }
    response = client.post("/acp/checkout_sessions", json=payload)
    assert response.status_code == 201, response.text
    session = response.json()
    validate("CheckoutSession", session)
    assert session["status"] == "requires_escalation"
    assert (
        client.post("/acp/checkout_sessions", json=payload).json()["id"]
        == session["id"]
    )
    assert (
        client.post(
            "/acp/checkout_sessions", json={**payload, "currency": "eur"}
        ).status_code
        == 409
    )
    path = f"/acp/checkout_sessions/{session['id']}"
    complete = client.post(
        path + "/complete",
        json={"payment_data": {"purchase_order_number": "TEST-PO-ONLY"}},
        headers={"Idempotency-Key": "complete-1"},
    )
    assert complete.status_code == 200, complete.text
    assert complete.json()["status"] == "requires_escalation"
    assert (
        buyers[0].get("/api/v1/workspace").json()["orders"][0]["payment_status"]
        == "NOT_STARTED"
    )
    assert (
        client.post(
            path + "/cancel", json={}, headers={"Idempotency-Key": "cancel-1"}
        ).json()["status"]
        == "canceled"
    )
    assert (
        buyers[0]
        .post(f"/api/v1/me/agent-access/{access['client_id']}/revoke")
        .status_code
        == 200
    )
    assert client.get(path).status_code == 401
    with app.state.store.transaction() as tx:
        assert "TEST-PO-ONLY" not in str(tx.all("acp_operations"))
        assert access["token"] not in str(tx.all("agent_access"))


def test_alembic_upgrade_preserves_existing_records(tmp_path):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    with Store(url).transaction() as tx:
        tx.put("meta", {"id": "preserve", "value": 42})
    env = {**os.environ, "DATABASE_URL": url}
    result = subprocess.run(
        [".venv/bin/python", "-m", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    with Store(url).transaction() as tx:
        assert tx.get("meta", "preserve")["value"] == 42


def test_inflight_payment_releases_database_lock_and_blocks_conflicting_actions(
    app, monkeypatch
):
    buyers, _, seller, pool = cleared(app)
    order = (
        buyers[0]
        .post(f"/api/v1/pools/{pool['id']}/approve", json={"version": pool["version"]})
        .json()
    )
    entered, release = Event(), Event()
    original = app.state.payments.create
    calls = []

    def delayed(snapshot):
        calls.append(snapshot["id"])
        entered.set()
        if not release.wait(8):
            raise PaymentError("Timed out waiting for test release")
        return original(snapshot)

    monkeypatch.setattr(app.state.payments, "create", delayed)
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = executor.submit(
            buyers[0].post, f"/api/v1/orders/{order['id']}/checkout"
        )
        assert entered.wait(3)
        try:
            independent = executor.submit(buyers[1].get, "/api/v1/workspace")
            assert independent.result(timeout=2).status_code == 200
            assert (
                buyers[0].post(f"/api/v1/orders/{order['id']}/checkout").status_code
                == 409
            )
            assert seller.post(f"/api/v1/pools/{pool['id']}/cancel").status_code == 409
        finally:
            release.set()
        assert pending.result(timeout=3).json()["payment_status"] == "CREATED"
    assert calls == [order["id"]]


def test_capture_timeout_preserves_delivery_and_durable_operation(app, monkeypatch):
    buyers, _, seller, pool = cleared(app)
    orders = [authorize(b, pool) for b in buyers]
    seller.post(
        f"/api/v1/pools/{pool['id']}/dispatch", json={"driver_id": "driver-demo"}
    )

    def uncertain(order):
        raise PaymentError("Capture outcome uncertain")

    monkeypatch.setattr(app.state.payments, "capture", uncertain)
    result = login(app, "driver").post(
        f"/api/v1/orders/{orders[0]['id']}/pod",
        json={
            "delivered_quantity": 30,
            "recipient_name": "Shop recipient",
            "acknowledgement": True,
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["pod"]["delivered_quantity"] == 30
    assert result.json()["payment_status"] == "REQUIRES_RECONCILIATION"
    with app.state.store.transaction() as tx:
        assert any(
            o["order_id"] == orders[0]["id"]
            and o["action"] == "capture"
            and o["status"] == "UNKNOWN"
            for o in tx.all("payment_operations")
        )


def test_failed_replan_keeps_completed_voids_and_auditable_replacement(
    app, monkeypatch
):
    buyers, requests, seller, pool = cleared(app)
    [authorize(b, pool) for b in buyers]
    from fastapi import HTTPException

    from app.platform import service

    def failed(*args):
        raise HTTPException(409, "Revised specifications need review")

    monkeypatch.setattr(service, "clear_pool", failed)
    result = seller.post(
        f"/api/v1/pools/{pool['id']}/replan?exclude_request_id={requests[2]['id']}"
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "FAILED"
    state = seller.get("/api/v1/workspace").json()
    assert (
        next(p for p in state["pools"] if p["id"] == pool["id"])["status"]
        == "CANCELLED"
    )
    assert all(o["payment_status"] == "VOIDED" for o in state["orders"])


def test_expired_final_quote_blocks_approval_and_releases_commitments(app):
    buyers, _, seller, pool = cleared(app)
    [authorize(b, pool) for b in buyers]
    with app.state.store.transaction() as tx:
        stored = tx.get("pools", pool["id"])
        stored["approval_expires_at"] = (
            datetime.now(UTC) - timedelta(minutes=1)
        ).isoformat()
        tx.put("pools", stored)
    assert (
        buyers[0]
        .post(f"/api/v1/pools/{pool['id']}/approve", json={"version": pool["version"]})
        .status_code
        == 409
    )
    worker.schedule(app.state.store, app.state.payments)
    assert all(
        o["payment_status"] == "VOIDED"
        for o in seller.get("/api/v1/workspace").json()["orders"]
    )


def test_feed_preparation_uses_real_base_price_and_reports_missing_fields(app):
    seller = login(app, "seller")
    initial = seller.get("/api/v1/seller/product-feed").json()
    assert len(initial["rejected"]) == 3 and initial["products"] == []
    with app.state.store.transaction() as tx:
        item = tx.get("products", "rice-sona")
        item.update(
            description="Harvest Sona Masoori rice, sold by the kilogram.",
            product_url="https://merchant.example/products/rice",
            image_url="https://merchant.example/images/rice.jpg",
        )
        tx.put("products", item)
    feed = seller.post("/api/v1/seller/product-feed/preview").json()
    assert len(feed["products"]) == 1
    assert feed["products"][0]["price"] == "1.80 USD"
    assert feed["products"][0]["is_eligible_checkout"] is False
    assert feed["published"] is False
    assert login(app, "a").get("/api/v1/seller/product-feed").status_code == 403


def test_exception_close_is_replay_safe_and_restores_only_declared_saleable_stock(app):
    buyers, _, seller, pool = cleared(app)
    orders = [authorize(b, pool) for b in buyers]
    seller.post(
        f"/api/v1/pools/{pool['id']}/dispatch", json={"driver_id": "driver-demo"}
    )
    login(app, "driver").post(
        f"/api/v1/orders/{orders[0]['id']}/pod",
        json={
            "delivered_quantity": 20,
            "recipient_name": "Shop recipient",
            "acknowledgement": True,
            "exception": "DAMAGED",
        },
    )
    body = {
        "action": "VOID_AND_CLOSE",
        "reason": "Merchant accepted returned goods",
        "returned_quantity": 5,
    }
    path = f"/api/v1/orders/{orders[0]['id']}/resolve-exception"
    first = seller.post(path, json=body)
    assert first.status_code == 200, first.text
    assert first.json()["payment_status"] == "VOIDED"
    assert seller.post(path, json=body).json()["status"] == "CANCELLED"
    product = next(
        p
        for p in seller.get("/api/v1/workspace").json()["products"]
        if p["id"] == "rice-sona"
    )
    assert product["stock"] == 415
