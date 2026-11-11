from io import BytesIO

from PIL import Image
from test_commerce import app as app
from test_commerce import authorize, buy, cleared, login


def image_bytes():
    result = BytesIO()
    Image.new("RGB", (20, 20), "blue").save(result, "PNG")
    return result.getvalue()


def profile(client, **fields):
    me = client.get("/api/v1/me").json()["user"]
    return client.patch(
        "/api/v1/me", json={"name": me["name"], "location": me["location"], **fields}
    )


def test_profile_persists_contacts_and_preferences_without_changing_login_or_roles(app):
    buyer, other = login(app, "a"), login(app, "b")
    response = profile(
        buyer,
        name="GreenMart Foods",
        contact_email="delivery@example.com",
        contact_phone="+91 1234567890",
        business_address="12 Market Road",
        city="Bengaluru",
        postal_code="560001",
        country="India",
        delivery_instructions="Use rear entrance",
        preferred_delivery_window="10:00–12:00",
        notifications_in_app=False,
    )
    assert response.status_code == 200, response.text
    saved = login(app, "a").get("/api/v1/me").json()["user"]
    assert saved["email"] == "ananya@paypool.demo" and saved["roles"] == ["RETAILER"]
    assert (
        saved["business_address"] == "12 Market Road"
        and saved["notifications_in_app"] is False
    )
    assert "delivery@example.com" not in other.get("/api/v1/workspace").text
    assert profile(buyer, location=[200, 0]).status_code == 422
    assert profile(buyer, contact_email="invalid").status_code == 422


def test_active_order_locks_address_but_not_contact_changes_and_snapshot_is_retained(
    app,
):
    buyer = login(app, "a")
    assert (
        profile(
            buyer, business_address="12 Market Road", contact_phone="12345"
        ).status_code
        == 200
    )
    buy(buyer)
    assert profile(buyer, contact_phone="67890").status_code == 200
    assert profile(buyer, business_address="99 Other Road").status_code == 409


def application():
    return dict(
        business_name="New Supplier",
        registration_number="GST-12345",
        business_address="12 Wholesale Street",
        contact_email="supply@example.com",
        contact_phone="123456789",
        catalog_summary="Rice, packaging and daily delivery routes",
    )


def test_supplier_application_rejection_resubmission_and_approval_are_scoped_and_versioned(
    app,
):
    buyer, other, admin = login(app, "a"), login(app, "b"), login(app, "admin")
    path = "/api/v1/me/seller-application"
    pending = buyer.post(path, json=application()).json()
    assert pending["status"] == "PENDING"
    assert other.get(path).json()["status"] == "NOT_SUBMITTED"
    assert buyer.get("/api/v1/admin/seller-applications").status_code == 403
    route = "/api/v1/admin/seller-applications/buyer-a/review"
    assert (
        buyer.post(
            route,
            json={"version": 1, "decision": "APPROVED", "note": "Reviewed business"},
        ).status_code
        == 403
    )
    rejected = admin.post(
        route,
        json={
            "version": 1,
            "decision": "REJECTED",
            "note": "Registration needs correction",
        },
    )
    assert rejected.json()["status"] == "REJECTED"
    assert buyer.get("/api/v1/me").json()["user"]["roles"] == ["RETAILER"]
    resubmitted = buyer.post(path, json=application()).json()
    assert (
        admin.post(
            route,
            json={"version": 1, "decision": "APPROVED", "note": "Reviewed business"},
        ).status_code
        == 409
    )
    approved = admin.post(
        route,
        json={
            "version": resubmitted["version"],
            "decision": "APPROVED",
            "note": "Business checked and approved",
        },
    )
    assert approved.status_code == 200
    assert "SELLER" in buyer.get("/api/v1/me").json()["user"]["roles"]


def test_account_disable_revokes_sessions_and_blocks_self_disable_and_outstanding_work(
    app,
):
    buyer, admin = login(app, "a"), login(app, "admin")
    assert (
        admin.post(
            "/api/v1/admin/users/admin-demo/state",
            json={"active": False, "reason": "Testing self disable"},
        ).status_code
        == 403
    )
    path = "/api/v1/admin/users/buyer-a/state"
    assert (
        admin.post(
            path, json={"active": False, "reason": "Business closed"}
        ).status_code
        == 200
    )
    assert buyer.get("/api/v1/me").status_code == 401
    assert (
        admin.post(
            path, json={"active": True, "reason": "Business reopened"}
        ).status_code
        == 200
    )
    buyer = login(app, "a")
    buy(buyer)
    assert (
        admin.post(
            path, json={"active": False, "reason": "Business closed"}
        ).status_code
        == 409
    )


def test_product_images_are_validated_bound_to_product_and_not_exported_as_public_feed(
    app,
):
    seller, buyer = login(app, "seller"), login(app, "a")
    path = "/api/v1/seller/products/rice-sona/image"
    assert (
        seller.post(
            path, files={"file": ("fake.png", b"<script>bad</script>", "image/png")}
        ).status_code
        == 422
    )
    assert (
        buyer.post(
            path, files={"file": ("photo.png", image_bytes(), "image/png")}
        ).status_code
        == 403
    )
    upload = seller.post(
        path, files={"file": ("photo.png", image_bytes(), "image/png")}
    )
    assert upload.status_code == 200, upload.text
    url = upload.json()["url"]
    response = buyer.get(url)
    assert (
        response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
    )
    assert response.headers["cache-control"] == "no-store"
    item = next(
        p
        for p in seller.get("/api/v1/workspace").json()["products"]
        if p["id"] == "rice-sona"
    )
    assert item["image_url"] == url
    item.update(description="Supplier rice", product_url="https://example.com/rice")
    item.pop("available_stock", None)
    seller.put(
        "/api/v1/seller/products/rice-sona",
        json={
            k: v
            for k, v in item.items()
            if k not in {"id", "seller_id", "stock_updated_at"}
        },
    )
    assert all(
        p["item_id"] != "rice-sona"
        for p in seller.get("/api/v1/seller/product-feed").json()["products"]
    )


def test_delivery_images_are_order_scoped_and_attached_to_append_only_pod(app):
    buyers, _, seller, pool = cleared(app)
    orders = [authorize(b, pool) for b in buyers]
    seller.post(
        f"/api/v1/pools/{pool['id']}/dispatch",
        json={"driver_id": "driver-demo", "vehicle_id": "demo-van"},
    )
    driver = login(app, "driver")
    upload = driver.post(
        f"/api/v1/orders/{orders[0]['id']}/evidence-image",
        files={"file": ("pod.png", image_bytes(), "image/png")},
    )
    assert upload.status_code == 200, upload.text
    data = upload.json()
    assert buyers[0].get(data["url"]).status_code == 200
    assert buyers[1].get(data["url"]).status_code == 403
    pod = {
        "delivered_quantity": 30,
        "recipient_name": "Recipient",
        "acknowledgement": True,
        "evidence_media_id": data["id"],
    }
    assert (
        driver.post(f"/api/v1/orders/{orders[1]['id']}/pod", json=pod).status_code
        == 403
    )
    response = driver.post(f"/api/v1/orders/{orders[0]['id']}/pod", json=pod)
    assert (
        response.status_code == 200
        and response.json()["pod"]["evidence_media_id"] == data["id"]
    )


def test_soft_target_cannot_exceed_or_change_the_hard_ceiling(app):
    buyer = login(app, "a")
    from datetime import date, timedelta

    payload = dict(
        product_id="rice-sona",
        zone_id="south-zone",
        dispatch_date=str(date.today() + timedelta(days=1)),
        quantity_min=30,
        quantity_max=30,
        ceiling_minor=170,
        target_price_minor=175,
    )
    assert buyer.post("/api/v1/procurement/requests", json=payload).status_code == 422
    payload["target_price_minor"] = 150
    saved = buyer.post("/api/v1/procurement/requests", json=payload).json()
    assert saved["target_price_minor"] == 150 and saved["ceiling_minor"] == 170


def test_notification_opt_out_keeps_payment_and_security_alerts(app):
    buyer = login(app, "a")
    profile(buyer, notifications_in_app=False)
    with app.state.store.transaction() as tx:
        tx.audit("buyer-a", "ROUTINE_TEST", "buyer-a")
        tx.audit("buyer-a", "PAYMENT_RECONCILIATION_REQUIRED", "buyer-a")
    notifications = buyer.get("/api/v1/workspace").json()["notifications"]
    assert not any(n["action"] == "ROUTINE_TEST" for n in notifications)
    assert any(n["action"] == "PAYMENT_RECONCILIATION_REQUIRED" for n in notifications)


def test_disabled_driver_cannot_receive_a_new_dispatch(app):
    buyers, _, seller, pool = cleared(app)
    for buyer in buyers:
        authorize(buyer, pool)
    admin = login(app, "admin")
    assert (
        admin.post(
            "/api/v1/admin/users/driver-demo/state",
            json={"active": False, "reason": "Driver unavailable"},
        ).status_code
        == 200
    )
    assert (
        seller.post(
            f"/api/v1/pools/{pool['id']}/dispatch",
            json={"driver_id": "driver-demo", "vehicle_id": "demo-van"},
        ).status_code
        == 409
    )


def test_model_target_is_optional_and_never_replaces_hard_limit():
    from app.modules.negotiation.llm import GeminiProcurementExtractor, LLMExtraction
    from app.modules.negotiation.procurement_schemas import ProcurementParseRequest

    request = ProcurementParseRequest(
        message="target 1.50, maximum delivered 1.70", currency="USD"
    )
    extracted = LLMExtraction(
        product_description="Rice",
        quantity=30,
        quantity_unit="kg",
        price_ceiling_per_unit_minor=170,
        target_price_per_unit_minor=150,
    )
    intent = GeminiProcurementExtractor._to_intent(request, extracted)
    assert (
        intent.target_price_per_unit_minor == 150
        and intent.price_ceiling_per_unit_minor == 170
    )
    invalid = extracted.model_copy(update={"target_price_per_unit_minor": 175})
    intent = GeminiProcurementExtractor._to_intent(request, invalid)
    assert (
        intent.target_price_per_unit_minor is None
        and intent.price_ceiling_per_unit_minor == 170
    )
    assert any("preferred target" in q for q in intent.clarification_questions)


def test_preferred_target_is_snapshotted_but_does_not_replace_hard_ceiling(app):
    from datetime import date, timedelta

    buyers = [login(app, n) for n in ("a", "b", "c")]
    requests = [
        b.post(
            "/api/v1/procurement/requests",
            json=dict(
                product_id="rice-sona",
                zone_id="south-zone",
                dispatch_date=str(date.today() + timedelta(days=1)),
                quantity_min=30,
                quantity_max=30,
                ceiling_minor=170,
                target_price_minor=150,
            ),
        ).json()
        for b in buyers
    ]
    pool = (
        login(app, "seller")
        .post(f"/api/v1/pools/{requests[0]['pool_id']}/clear")
        .json()
    )
    assert pool["status"] == "CLEARED"
    assert all(
        a["target_price_minor"] == 150
        and 150 * a["quantity"] < a["total_minor"] <= 170 * a["quantity"]
        for a in pool["allocations"]
    )


def test_profile_rename_does_not_rewrite_existing_receipt_party(app):
    buyers, _, _, pool = cleared(app)
    order = (
        buyers[0]
        .post(f"/api/v1/pools/{pool['id']}/approve", json={"version": pool["version"]})
        .json()
    )
    assert profile(buyers[0], name="Renamed GreenMart").status_code == 200
    receipt = buyers[0].get(f"/api/v1/orders/{order['id']}/receipt.html")
    assert receipt.status_code == 200
    assert (
        order["buyer_name"] in receipt.text and "Renamed GreenMart" not in receipt.text
    )
