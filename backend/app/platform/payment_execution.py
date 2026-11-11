"""Persist intent, release SQL locks, execute provider call, then reconcile result.

The order's persisted operation blocks conflicting void/capture/checkout actions.
Provider request IDs remain stable. Crashes leave an inspectable operation rather
than losing the fact that an external request might have been sent.
"""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from fastapi import HTTPException

from app.platform import service
from app.platform.payments import PaymentError
from app.platform.store import now


class Planned(Exception):
    pass


class PlanningProvider:
    def __init__(self, mode):
        self.mode = mode

    def __getattr__(self, name):
        def plan(*args, **kwargs):
            raise Planned()

        return plan


class CompletedProvider:
    def __init__(self, mode, result):
        self.mode, self.result = mode, result

    def __getattr__(self, name):
        return lambda *args, **kwargs: self.result


def execute(store, user, order_id, payments, action):
    method = {
        "checkout": "create",
        "authorize": "authorize",
        "capture": "capture",
        "void": "void",
    }[action]
    operation_id = sha256(f"{order_id}:{action}".encode()).hexdigest()
    with store.transaction() as tx:
        order = service.must(tx, "orders", order_id)
        # Plan through the same authoritative validation as synchronous callers.
        # This adapter cannot perform network I/O or move money.
        try:
            return service.payment_action(
                tx, user, order, PlanningProvider(payments.mode), action
            )
        except Planned:
            pass
        existing = tx.get("payment_operations", operation_id)
        if existing and existing["status"] in {"IN_FLIGHT", "UNKNOWN"}:
            raise HTTPException(
                409,
                "This payment operation requires reconciliation before another attempt",
            )
        order["payment_operation_id"] = operation_id
        order["capture_requested"] = False
        tx.put("orders", order)
        operation = tx.put(
            "payment_operations",
            {
                "id": operation_id,
                "order_id": order_id,
                "action": action,
                "actor": user["id"],
                "status": "IN_FLIGHT",
                "started_at": now(),
                "lease_until": (datetime.now(UTC) + timedelta(seconds=90)).isoformat(),
                "attempts": (existing or {}).get("attempts", 0) + 1,
            },
        )
    try:
        remote = getattr(payments, method)(order)
        failure = None
    except PaymentError as error:
        remote, failure = None, str(error)
    except (KeyError, TypeError, ValueError):
        remote, failure = (
            None,
            "Provider returned an incomplete response; reconcile before continuing",
        )
    with store.transaction() as tx:
        latest = service.must(tx, "orders", order_id)
        if latest.get("payment_operation_id") != operation_id:
            raise HTTPException(
                409, "Payment operation changed; reconcile provider state"
            )
        latest.pop("payment_operation_id", None)
        if failure:
            latest.update(
                payment_status="REQUIRES_RECONCILIATION",
                payment_error=failure,
                uncertain_action=action,
            )
            tx.put("orders", latest)
            tx.audit(
                user["id"],
                "PAYMENT_RECONCILIATION_REQUIRED",
                order_id,
                {"operation_id": operation_id, "action": action},
            )
        else:
            latest = service.payment_action(
                tx,
                user,
                latest,
                CompletedProvider(payments.mode, remote),
                action,
                settling_operation=True,
            )
        tx.put("orders", latest)
        operation.update(
            status="UNKNOWN"
            if latest["payment_status"] == "REQUIRES_RECONCILIATION"
            else "SUCCEEDED",
            finished_at=now(),
        )
        tx.put("payment_operations", operation)
        return latest


def cancel_pool(store, user, pool_id, payments):
    with store.transaction() as tx:
        pool = service.must(tx, "pools", pool_id)
        service.seller_access(user, pool["seller_id"])
        if pool["status"] == "CANCELLED":
            return pool
        if pool["status"] in {"DISPATCHED", "COMPLETED"}:
            raise HTTPException(
                409, "A dispatched run requires delivery-exception or refund handling"
            )
        orders = [o for o in tx.all("orders") if o["pool_id"] == pool_id]
        if any(
            o.get("payment_operation_id")
            or o["payment_status"]
            not in {"NOT_STARTED", "CREATED", "AUTHORIZED", "VOIDED"}
            for o in orders
        ):
            raise HTTPException(
                409, "Reconcile outstanding payment operations before cancellation"
            )
        pool["status"] = "CANCEL_PENDING"
        tx.put("pools", pool)
    for order in orders:
        execute(store, user, order["id"], payments, "void")
    with store.transaction() as tx:
        pool = service.must(tx, "pools", pool_id)
        pending = any(
            o["pool_id"] == pool_id and o["payment_status"] != "VOIDED"
            for o in tx.all("orders")
        )
        pool["status"] = "CANCEL_PENDING" if pending else "CANCELLED"
        tx.put("pools", pool)
        tx.audit(
            user["id"], "POOL_CANCEL_PENDING" if pending else "POOL_CANCELLED", pool_id
        )
        return pool


class DetachedWrites:
    def __init__(self, refunds):
        self.refunds = deepcopy(refunds)
        self.writes = []

    def all(self, kind):
        return self.refunds if kind == "refunds" else []

    def put(self, kind, value):
        self.writes.append((kind, deepcopy(value)))
        return value


def reconcile(store, user, order_id, payments, force=False):
    with store.transaction() as tx:
        original = service.must(tx, "orders", order_id)
        service.order_access(tx, user, original)
        operation = tx.get(
            "payment_operations", original.get("payment_operation_id", "")
        )
        if (
            operation
            and operation["status"] == "IN_FLIGHT"
            and datetime.fromisoformat(operation["lease_until"]) > datetime.now(UTC)
            and not force
        ):
            raise HTTPException(
                409,
                "The provider operation is still in flight; wait before reconciliation",
            )
        refunds = [r for r in tx.all("refunds") if r["order_id"] == order_id]
    detached = DetachedWrites(refunds)
    refreshed = service.reconcile(detached, deepcopy(original), payments)
    with store.transaction() as tx:
        latest = service.must(tx, "orders", order_id)
        # Preserve concurrent domain or verified provider updates.
        if latest != original:
            return latest
        for kind, value in detached.writes:
            if kind == "refunds":
                tx.put(kind, value)
        if operation and refreshed["payment_status"] not in {
            "REQUIRES_RECONCILIATION",
            "REFUND_PENDING",
            "CAPTURE_PENDING",
        }:
            refreshed.pop("payment_operation_id", None)
            operation.update(status="RECONCILED", finished_at=now())
            if (
                operation["action"] == "capture"
                and refreshed["payment_status"] == "AUTHORIZED"
            ):
                refreshed["capture_requested"] = True
            tx.put("payment_operations", operation)
        # Also release an UNKNOWN operation whose actor-visible error is now
        # resolved. It may have finished before an application restart.
        for pending in tx.all("payment_operations"):
            if (
                pending["order_id"] == order_id
                and pending["status"] == "UNKNOWN"
                and refreshed["payment_status"]
                not in {"REQUIRES_RECONCILIATION", "REFUND_PENDING", "CAPTURE_PENDING"}
            ):
                pending.update(status="RECONCILED", finished_at=now())
                tx.put("payment_operations", pending)
        tx.put("orders", refreshed)
        tx.audit(
            user["id"],
            "PAYMENT_RECONCILED",
            order_id,
            {"state": refreshed["payment_status"]},
        )
        return refreshed


def refund(store, user, order_id, data, key, payments):
    if not 8 <= len(key) <= 100:
        raise HTTPException(422, "Provide an Idempotency-Key of 8–100 characters")
    identity = sha256(f"{order_id}:{key}".encode()).hexdigest()
    with store.transaction() as tx:
        order = service.must(tx, "orders", order_id)
        service.seller_access(user, order["seller_id"])
        previous = tx.get("refunds", identity)
        if previous:
            if (
                previous["amount_minor"] != data.amount_minor
                or previous["reason"] != data.reason
            ):
                raise HTTPException(409, "This key belongs to different refund terms")
            return previous
        if order.get("payment_operation_id") or order["payment_status"] not in {
            "CAPTURED",
            "PARTIALLY_REFUNDED",
        }:
            raise HTTPException(
                409, "A confirmed capture with no pending operation is required"
            )
        if data.amount_minor > order["total_minor"] - order["refunded_minor"]:
            raise HTTPException(409, "Refund exceeds the remaining captured amount")
        record = tx.put(
            "refunds",
            {
                "id": identity,
                "order_id": order_id,
                **data.model_dump(),
                "created_at": now(),
                "status": "PENDING",
            },
        )
        order["payment_status"] = "REFUND_PENDING"
        tx.put("orders", order)
    try:
        remote = payments.refund(order, data.amount_minor, "refund:" + identity)
        if not isinstance(remote.get("id"), str) or not remote["id"]:
            raise PaymentError(
                "Provider refund reference is missing; reconcile before continuing"
            )
        record.update(provider_refund_id=remote["id"], status=remote["status"])
    except (PaymentError, KeyError, TypeError, ValueError) as error:
        record.update(
            status="REQUIRES_RECONCILIATION",
            error=str(error)
            if isinstance(error, PaymentError)
            else "Refund response is uncertain; reconcile before continuing",
        )
    with store.transaction() as tx:
        latest = service.must(tx, "orders", order_id)
        existing_refund = service.must(tx, "refunds", identity)
        if existing_refund["status"] == "COMPLETED":
            record = existing_refund
        tx.put("refunds", record)
        if record["status"] == "COMPLETED":
            completed = sum(
                r["amount_minor"]
                for r in tx.all("refunds")
                if r["order_id"] == order_id and r["status"] == "COMPLETED"
            )
            latest["refunded_minor"] = completed
            latest["payment_status"] = (
                "REFUNDED"
                if completed == latest["total_minor"]
                else "PARTIALLY_REFUNDED"
            )
        elif record["status"] == "REQUIRES_RECONCILIATION":
            latest.update(
                payment_status="REQUIRES_RECONCILIATION", payment_error=record["error"]
            )
        tx.put("orders", latest)
        tx.audit(
            user["id"],
            "REFUND_REQUESTED",
            order_id,
            {
                "refund_id": identity,
                "amount_minor": data.amount_minor,
                "state": latest["payment_status"],
            },
        )
        return record
