"""Durable, at-least-once outbox and schedule processing.

Run `python -m app.platform.worker --once` or continuously. Celery can call the
same tick function; the database is the durable queue and deduplication layer.
"""

import argparse
import os
import time
from datetime import UTC, date, datetime, timedelta

from dotenv import load_dotenv
from fastapi import HTTPException

from app.platform import payment_execution, service
from app.platform.payments import PaymentError, Payments
from app.platform.schedules import cutoff_passed
from app.platform.store import Store, now


def schedule(store, payments, at=None):
    at = at or datetime.now(UTC)
    processed = 0
    expired = []
    with store.transaction() as tx:
        for instruction in tx.all("standing_orders"):
            if not instruction["active"]:
                continue
            target = date.fromisoformat(instruction["next_dispatch_date"])
            if instruction.get("end_date") and target > date.fromisoformat(
                instruction["end_date"]
            ):
                instruction.update(active=False, status="EXPIRED")
                tx.put("standing_orders", instruction)
                continue
            if target > at.date() + timedelta(days=instruction["lookahead_days"]):
                continue
            occurrence = f"{instruction['id']}:{target.isoformat()}"
            if tx.get("standing_occurrences", occurrence):
                continue
            user = service.must(tx, "users", instruction["buyer_id"])
            if not user.get("active", True) or "RETAILER" not in user["roles"]:
                instruction.update(
                    active=False,
                    status="REVIEW_REQUIRED",
                    last_error="Account is unavailable",
                )
                tx.put("standing_orders", instruction)
                continue
            savepoint = tx.connection.begin_nested()
            try:
                for sku, expected in instruction[
                    "approved_product_specifications"
                ].items():
                    if (
                        service.product_specification(service.must(tx, "products", sku))
                        != expected
                    ):
                        raise HTTPException(
                            409,
                            "Catalog specifications changed; review the buying instruction",
                        )
                buying = service.submit_request(
                    tx,
                    user,
                    {**instruction["request"], "dispatch_date": target.isoformat()},
                )
                savepoint.commit()
                tx.put(
                    "standing_occurrences",
                    {
                        "id": occurrence,
                        "standing_id": instruction["id"],
                        "request_id": buying["id"],
                        "at": now(),
                    },
                )
                instruction.update(
                    next_dispatch_date=(
                        target + timedelta(days=instruction["repeat_days"])
                    ).isoformat(),
                    last_request_id=buying["id"],
                    status="ACTIVE",
                )
                instruction.pop("last_error", None)
            except (HTTPException, ValueError) as error:
                savepoint.rollback()
                instruction.update(
                    active=False,
                    status="REVIEW_REQUIRED",
                    last_error=str(getattr(error, "detail", error)),
                )
                tx.audit(
                    user["id"],
                    "STANDING_ORDER_REVIEW_REQUIRED",
                    instruction["id"],
                    {"reason": instruction["last_error"]},
                )
            tx.put("standing_orders", instruction)
            processed += 1
        for pool in tx.all("pools"):
            zone = service.must(tx, "zones", pool["zone_id"])
            if (
                pool["status"] == "CLEARED"
                and pool.get("approval_expires_at")
                and datetime.fromisoformat(pool["approval_expires_at"]) <= at
            ) or pool["status"] == "CANCEL_PENDING":
                expired.append(
                    (pool["id"], service.must(tx, "users", pool["seller_id"]))
                )
                continue
            if (
                pool["status"] == "ACCUMULATING"
                and cutoff_passed(pool, at)
                and zone.get("auto_clear_at_cutoff", True)
            ):
                seller = service.must(tx, "users", pool["seller_id"])
                if not seller.get("active", True) or not seller.get("verified", False):
                    continue
                savepoint = tx.connection.begin_nested()
                try:
                    service.clear_pool(tx, seller, pool)
                    savepoint.commit()
                except (HTTPException, ValueError) as error:
                    savepoint.rollback()
                    pool.update(
                        status="FAILED", reason=str(getattr(error, "detail", error))
                    )
                    tx.put("pools", pool)
                    tx.audit(
                        seller["id"],
                        "POOL_FAILED",
                        pool["id"],
                        {"reason": pool["reason"]},
                    )
                processed += 1
    for pool_id, seller in expired:
        try:
            payment_execution.cancel_pool(store, seller, pool_id, payments)
            processed += 1
        except HTTPException:
            with store.transaction() as tx:
                tx.audit(seller["id"], "EXPIRED_POOL_RECONCILIATION_REQUIRED", pool_id)
    return processed


def process_event(store, event_id):
    # External search indexing is idempotent and runs without a SQL lock.
    with store.transaction() as tx:
        queued = service.must(tx, "outbox", event_id)
        product = (
            tx.get("products", queued["payload"]["subject"])
            if queued["status"] != "DELIVERED"
            else None
        )
    if product and os.getenv("ELASTICSEARCH_URL"):
        from app.platform.search import ElasticSearch

        ElasticSearch().index_product(product)
    # The handler and delivery mark commit together. A worker crash rolls both
    # back; retrying uses deterministic projection keys instead of duplicates.
    with store.transaction() as tx:
        event = service.must(tx, "outbox", event_id)
        if event["status"] == "DELIVERED" or datetime.fromisoformat(
            event["next_attempt_at"]
        ) > datetime.now(UTC):
            return False
        payload = event["payload"]
        order = tx.get("orders", payload["subject"])
        if order:
            tx.put(
                "receipt_records",
                {
                    **service.smart_receipt(order),
                    "id": order["id"],
                    "source_event_id": event_id,
                },
            )
            if payload["action"].startswith(("PAYMENT_", "REFUND_")):
                tx.put(
                    "payment_ledger",
                    {
                        "id": event_id,
                        "order_id": order["id"],
                        "seller_id": order["seller_id"],
                        "buyer_id": order["buyer_id"],
                        "action": payload["action"],
                        "payment_status": payload.get("details", {}).get(
                            "state", order["payment_status"]
                        ),
                        "operation_amount_minor": payload.get("details", {}).get(
                            "amount_minor"
                        ),
                        "currency": order["currency"],
                        "total_minor": order["total_minor"],
                        "refunded_minor": order.get("refunded_minor", 0),
                        "at": event["occurred_at"],
                    },
                )
        event.update(
            status="DELIVERED", delivered_at=now(), attempts=event["attempts"] + 1
        )
        tx.put("outbox", event)
        return True


def tick(store=None, payments=None, limit=100):
    store = store or Store()
    payments = payments or Payments(
        os.getenv("PAYPOOL_DEMO_MODE", "true").lower() == "true"
    )
    result = {
        "scheduled": schedule(store, payments),
        "delivered": 0,
        "failed": 0,
        "reconciled": 0,
    }
    with store.transaction() as tx:
        jobs = [
            e["id"]
            for e in tx.all("outbox")
            if e["status"] in {"PENDING", "RETRY"}
            and datetime.fromisoformat(e["next_attempt_at"]) <= datetime.now(UTC)
        ][:limit]
        pending = [
            o["id"]
            for o in tx.all("orders")
            if o["payment_status"]
            in {"REQUIRES_RECONCILIATION", "CAPTURE_PENDING", "REFUND_PENDING"}
            or o.get("payment_operation_id")
        ]
    for event_id in jobs:
        try:
            result["delivered"] += int(process_event(store, event_id))
        except Exception:
            # The queue records sanitized failure metadata, never exception
            # bodies that might contain provider credentials or user content.
            with store.transaction() as tx:
                event = service.must(tx, "outbox", event_id)
                event["attempts"] += 1
                event.update(
                    status="DEAD_LETTER" if event["attempts"] >= 5 else "RETRY",
                    error="Projection processing failed",
                    next_attempt_at=(
                        datetime.now(UTC)
                        + timedelta(seconds=min(3600, 2 ** event["attempts"] * 10))
                    ).isoformat(),
                )
                tx.put("outbox", event)
            result["failed"] += 1
    for order_id in pending[:20]:
        with store.transaction() as tx:
            order = service.must(tx, "orders", order_id)
            actor = service.must(tx, "users", order["seller_id"])
            if order.get("reconcile_after") and datetime.fromisoformat(
                order["reconcile_after"]
            ) > datetime.now(UTC):
                continue
        if payments.mode != "demo":
            try:
                payment_execution.reconcile(store, actor, order_id, payments)
                result["reconciled"] += 1
            except (PaymentError, HTTPException, KeyError, ValueError):
                pass
            with store.transaction() as tx:
                current = service.must(tx, "orders", order_id)
                current["reconcile_after"] = (
                    datetime.now(UTC) + timedelta(minutes=5)
                ).isoformat()
                tx.put("orders", current)
    if payments.mode != "demo":
        with store.transaction() as tx:
            events = [
                e
                for e in tx.all("payment_events")
                if e.get("status") == "PENDING" and e.get("order_id")
            ][:20]
        for event in events:
            with store.transaction() as tx:
                order = service.must(tx, "orders", event["order_id"])
                actor = service.must(tx, "users", order["seller_id"])
            try:
                payment_execution.reconcile(store, actor, order["id"], payments)
                with store.transaction() as tx:
                    saved = service.must(tx, "payment_events", event["id"])
                    saved["status"] = "PROCESSED"
                    tx.put("payment_events", saved)
            except (PaymentError, HTTPException):
                pass
    with store.transaction() as tx:
        captures = [
            (o["id"], service.must(tx, "users", o["seller_id"]))
            for o in tx.all("orders")
            if o.get("capture_requested")
            and not o.get("payment_operation_id")
            and o["payment_status"] == "AUTHORIZED"
        ]
    for order_id, actor in captures[:20]:
        try:
            payment_execution.execute(store, actor, order_id, payments, "capture")
        except HTTPException:
            pass
    with store.transaction() as tx:
        tx.put(
            "worker_health",
            {"id": "commerce-worker", "last_tick": now(), "result": result},
        )
    return result


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()
    while True:
        print(tick(), flush=True)
        if args.once:
            break
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()
