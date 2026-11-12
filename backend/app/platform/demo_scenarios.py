"""Reproducible fictional walkthroughs, built through real domain transitions.

Run only against a fresh, simulator-only database before starting the server.
Existing scenarios are returned unchanged; existing user purchases are refused.
"""

import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.platform import payment_execution, service
from app.platform.models import Delivery, Request
from app.platform.payments import Payments
from app.platform.seed import seed
from app.platform.store import Store, now

SCENARIO_KEY = "recording-scenarios-v1"
BUYERS = ("buyer-a", "buyer-b", "buyer-c")


def prepare(store):
    if os.getenv("PAYPOOL_DEMO_MODE", "false").lower() != "true":
        raise ValueError("Recording scenarios require PAYPOOL_DEMO_MODE=true")
    payments = Payments(demo=True)
    if payments.mode != "demo":
        raise ValueError("Recording scenarios require simulated payments")
    with store.transaction() as tx:
        previous = tx.get("meta", SCENARIO_KEY)
        if previous:
            return previous
        if any(tx.all(kind) for kind in ("requests", "pools", "orders")):
            raise ValueError(
                "Use a fresh demo database; existing purchases are preserved"
            )
    seed(store)
    with store.transaction() as tx:
        people = {
            key: service.must(tx, "users", key)
            for key in (*BUYERS, "seller-demo", "driver-demo")
        }
    seller, driver = people["seller-demo"], people["driver-demo"]
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()

    def make_run(offset, clear=False, dispatch=False, delivered=()):
        day = (today + timedelta(days=offset)).isoformat()
        requests = []
        for key in BUYERS:
            data = Request(
                product_id="rice-sona",
                zone_id="south-zone",
                dispatch_date=day,
                quantity_min=30,
                quantity_max=30,
                ceiling_minor=170,
                note="Fictional prepared demo request; no real purchase.",
            ).model_dump(mode="json")
            with store.transaction() as tx:
                requests.append(service.submit_request(tx, people[key], data))
        pool_id = requests[0]["pool_id"]
        orders = []
        if clear:
            with store.transaction() as tx:
                pool = service.clear_pool(
                    tx, seller, service.must(tx, "pools", pool_id)
                )
                if pool["status"] != "CLEARED":
                    raise ValueError("Prepared demo requirements could not clear")
            for key in BUYERS:
                with store.transaction() as tx:
                    order = service.approve(
                        tx,
                        people[key],
                        service.must(tx, "pools", pool_id),
                        pool["version"],
                    )
                for action in ("checkout", "authorize"):
                    payment_execution.execute(
                        store, people[key], order["id"], payments, action
                    )
                orders.append({"buyer_id": key, "order_id": order["id"]})
        if dispatch:
            with store.transaction() as tx:
                service.dispatch(
                    tx,
                    seller,
                    service.must(tx, "pools", pool_id),
                    driver["id"],
                    "demo-van",
                )
            for item in orders:
                if item["buyer_id"] not in delivered:
                    continue
                data = Delivery(
                    delivered_quantity=30,
                    recipient_name=people[item["buyer_id"]]["name"],
                    acknowledgement=True,
                    note="Fictional prepared demo delivery.",
                ).model_dump(mode="json")
                with store.transaction() as tx:
                    order = service.delivery(
                        tx,
                        driver,
                        service.must(tx, "orders", item["order_id"]),
                        data,
                        payments,
                        defer_capture=True,
                    )
                if order.get("capture_requested"):
                    payment_execution.execute(
                        store, driver, order["id"], payments, "capture"
                    )
        return {
            "date": day,
            "pool_id": pool_id,
            "requests": {r["buyer_id"]: r["id"] for r in requests},
            "orders": orders,
        }

    ready = make_run(1)
    recovery = make_run(2, clear=True)
    # Finish the receipt route before assigning Kiran's open recording route.
    receipts = make_run(4, clear=True, dispatch=True, delivered=BUYERS)
    delivery = make_run(3, clear=True, dispatch=True, delivered=BUYERS[1:])
    scenes = {
        "ready_to_clear": ready,
        "withdrawal_recovery": recovery,
        "delivery_evidence": delivery,
        "matched_receipts": receipts,
    }
    with store.transaction() as tx:
        return tx.put(
            "meta", {"id": SCENARIO_KEY, "created_at": now(), "scenarios": scenes}
        )


if __name__ == "__main__":
    # The caller must explicitly select the target database and simulation mode.
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("DATABASE_URL must point to a fresh demo database")
    print(json.dumps(prepare(Store()), indent=2))
