"""Optional real-service checks. URLs must point to disposable test services."""

import os
import subprocess
import time

import pytest
from celery import Celery
from test_commerce import authorize, cleared, login

from app.main import create_app
from app.platform.store import Store


@pytest.mark.skipif(
    not os.getenv("PAYPOOL_TEST_POSTGRES_URL"),
    reason="Disposable PostgreSQL URL not supplied",
)
def test_real_postgres_fulfillment_and_worker(monkeypatch):
    monkeypatch.setenv("PAYPOOL_POSTGIS", "false")
    application = create_app(os.environ["PAYPOOL_TEST_POSTGRES_URL"], demo=True)
    buyers, _, seller, pool = cleared(application)
    orders = [authorize(b, pool) for b in buyers]
    result = seller.post(
        f"/api/v1/pools/{pool['id']}/dispatch",
        json={"driver_id": "driver-demo", "vehicle_id": "demo-van"},
    )
    assert result.status_code == 200, result.text
    driver = login(application, "driver")
    for order in orders:
        delivered = driver.post(
            f"/api/v1/orders/{order['id']}/pod",
            json={
                "delivered_quantity": 30,
                "recipient_name": "Postgres recipient",
                "acknowledgement": True,
            },
        )
        assert delivered.json()["payment_status"] == "CAPTURED"
    from app.platform.worker import tick

    assert (
        tick(application.state.store, application.state.payments, limit=500)[
            "delivered"
        ]
        > 0
    )
    assert (
        buyers[0].get(f"/api/v1/orders/{orders[0]['id']}/receipt").json()["status"]
        == "MATCHED"
    )


@pytest.mark.skipif(
    not os.getenv("PAYPOOL_TEST_REDIS_URL"), reason="Disposable Redis URL not supplied"
)
def test_real_redis_celery_consumes_durable_event(tmp_path):
    url = f"sqlite:///{tmp_path / 'celery.db'}"
    store = Store(url)
    with store.transaction() as tx:
        event = tx.audit("integration-worker", "INTEGRATION_TEST", "no-customer-data")
    env = {
        **os.environ,
        "DATABASE_URL": url,
        "PAYPOOL_POSTGIS": "false",
        "REDIS_URL": os.environ["PAYPOOL_TEST_REDIS_URL"],
        "PAYPOOL_DEMO_MODE": "true",
        "PAYPOOL_PAYMENT_PROVIDER": "demo",
    }
    process = subprocess.Popen(
        [
            ".venv/bin/python",
            "-m",
            "celery",
            "-A",
            "app.platform.tasks",
            "worker",
            "--pool=solo",
            "--concurrency=1",
            "--loglevel=WARNING",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        client = Celery("paypool-service-check", broker=env["REDIS_URL"])
        client.send_task("paypool.commerce_tick")
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            with store.transaction() as tx:
                if tx.get("outbox", event["id"])["status"] == "DELIVERED":
                    assert tx.get("worker_health", "commerce-worker")
                    return
            assert process.poll() is None, "Celery worker exited before processing"
            time.sleep(0.2)
        pytest.fail("Celery did not consume the durable event within the deadline")
    finally:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
