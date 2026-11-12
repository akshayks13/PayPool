from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from test_commerce import app as app

from app.platform.judge_examples import prepare


def registration():
    return {
        "name": "Judge Test Shop",
        "email": "judge@example.com",
        "password": "Test-workspace-2026!",
    }


def test_registration_session_privacy_and_retailer_scope(app):
    c = TestClient(app)
    r = c.post("/api/v1/auth/register", json=registration())
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["user"]["roles"] == ["RETAILER"] and not d["user"]["verified"]
    assert "password_hash" not in d["user"]
    assert c.get("/api/v1/me").json()["user"]["email"] == "judge@example.com"
    assert c.get("/api/v1/admin/operations").status_code == 403
    assert (
        c.post(
            "/api/v1/auth/register",
            json={**registration(), "email": "JUDGE@example.com"},
        ).status_code
        == 409
    )
    fresh = TestClient(app)
    assert (
        fresh.post(
            "/api/v1/auth/login",
            json={"email": "judge@example.com", "password": registration()["password"]},
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "override",
    [
        {"password": "short"},
        {"roles": ["ADMIN"]},
        {"email": "new@paypool.demo"},
        {"email": "invalid"},
    ],
)
def test_signup_rejects_weak_credentials_or_role_injection(app, override):
    assert (
        TestClient(app)
        .post("/api/v1/auth/register", json={**registration(), **override})
        .status_code
        == 422
    )


def test_signup_checks_origin_and_demo_boundary(app):
    c = TestClient(app)
    assert (
        c.post(
            "/api/v1/auth/register",
            json=registration(),
            headers={"Origin": "https://other.example"},
        ).status_code
        == 403
    )
    app.state.demo = False
    assert c.post("/api/v1/auth/register", json=registration()).status_code == 403


def test_judge_examples_are_idempotent_and_never_invent_payment_records(app):
    store = app.state.store
    first = prepare(store)
    assert prepare(store) == first
    with store.transaction() as tx:
        assert len(tx.all("requests")) == 5
        assert not tx.all("orders") and not tx.all("payment_operations")
        pools = [tx.get("pools", s["pool_id"]) for s in first["scenes"]]
        assert sorted(p["status"] for p in pools) == ["ACCUMULATING", "CLEARED"]
        quote = next(p for p in pools if p["status"] == "CLEARED")
        assert [a["total_minor"] for a in quote["allocations"]] == [4900, 4900]
        assert all(
            p["dispatch_date"]
            > datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
            for p in pools
        )
