import json
from datetime import date
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import HTTPException

from app.platform import clearing
from app.platform.auth import require_role
from app.platform.payments import PaymentError
from app.platform.store import now


def must(tx, kind, key):
    value = tx.get(kind, key)
    if value is None:
        raise HTTPException(404, f"{kind.rstrip('s').title()} not found")
    return value


def seller_access(user, seller_id):
    require_role(user, "SELLER", "ADMIN")
    if "ADMIN" not in user["roles"] and user["id"] != seller_id:
        raise HTTPException(403, "This record belongs to another distributor")


def order_access(tx, user, order):
    allowed = (
        user["id"] in {order["buyer_id"], order["seller_id"]}
        or "ADMIN" in user["roles"]
    )
    if "DRIVER" in user["roles"]:
        allowed |= must(tx, "pools", order["pool_id"]).get("driver_id") == user["id"]
    if not allowed:
        raise HTTPException(403, "This order is not assigned to you")


def available_stock(tx, exclude_pool=None):
    stock = {p["id"]: p["stock"] for p in tx.all("products")}
    for pool in tx.all("pools"):
        if pool["id"] == exclude_pool or pool["status"] not in {
            "CLEARED",
            "DISPATCHED",
            "CANCEL_PENDING",
        }:
            continue
        for a in pool.get("allocations", []):
            stock[a["product_id"]] = stock.get(a["product_id"], 0) - a["quantity"]
    return stock


def product_specification(product):
    return {key: product[key] for key in ("title", "unit", "currency", "attributes")}


def submit_request(tx, user, data):
    require_role(user, "RETAILER")
    item, zone = (
        must(tx, "products", data["product_id"]),
        must(tx, "zones", data["zone_id"]),
    )
    if not inside_zone(user, zone, tx) or item["seller_id"] != zone["seller_id"]:
        raise HTTPException(
            422, "This product cannot be delivered to your location by this distributor"
        )
    if item["currency"] != zone.get("currency", "USD"):
        raise HTTPException(
            422, "Product and freight configuration must use the same currency"
        )
    if not must(tx, "users", item["seller_id"]).get("verified", False):
        raise HTTPException(
            409, "Distributor must be verified before accepting requests"
        )
    if date.fromisoformat(data["dispatch_date"]) < date.today():
        raise HTTPException(422, "Delivery date is in the past")
    for sku in data.get("substitute_product_ids", []):
        alt = must(tx, "products", sku)
        if (
            alt["seller_id"] != item["seller_id"]
            or alt["currency"] != item["currency"]
            or alt["unit"] != item["unit"]
        ):
            raise HTTPException(
                422, "Substitutes must use the same distributor, currency and unit"
            )
        for attr in ("variety", "size", "material"):
            if item.get("attributes", {}).get(attr) != alt.get("attributes", {}).get(
                attr
            ):
                raise HTTPException(
                    422, f"Substitute changes protected attribute: {attr}"
                )
    pool = next(
        (
            p
            for p in tx.all("pools")
            if p["zone_id"] == zone["id"]
            and p["dispatch_date"] == data["dispatch_date"]
            and p["currency"] == item["currency"]
            and p["status"] in {"ACCUMULATING", "FAILED"}
        ),
        None,
    )
    if pool is None:
        pool = {
            "id": str(uuid4()),
            "seller_id": item["seller_id"],
            "zone_id": zone["id"],
            "dispatch_date": data["dispatch_date"],
            "currency": item["currency"],
            "status": "ACCUMULATING",
            "version": 0,
            "request_ids": [],
            "allocations": [],
            "created_at": now(),
        }
    existing = [must(tx, "requests", key) for key in pool["request_ids"]]
    if any(r["buyer_id"] == user["id"] and r["status"] == "ACTIVE" for r in existing):
        raise HTTPException(
            409,
            "One buying request per retailer per delivery run; withdraw the old request to replace it",
        )
    if len([r for r in existing if r["status"] == "ACTIVE"]) >= 6:
        raise HTTPException(
            409, "This delivery run has reached the MVP limit of six retailers"
        )
    record = tx.put(
        "requests",
        {
            **data,
            "id": str(uuid4()),
            "buyer_id": user["id"],
            "seller_id": item["seller_id"],
            "currency": item["currency"],
            "pool_id": pool["id"],
            "status": "ACTIVE",
            "approved_product_specifications": {
                sku: product_specification(must(tx, "products", sku))
                for sku in [item["id"], *data.get("substitute_product_ids", [])]
            },
            "created_at": now(),
        },
    )
    pool["request_ids"].append(record["id"])
    pool["status"] = "ACCUMULATING"
    tx.put("pools", pool)
    tx.audit(user["id"], "REQUEST_SUBMITTED", record["id"], {"pool_id": pool["id"]})
    return record


def inside_zone(user, zone, tx=None):
    if tx is not None and tx.postgis:
        return tx.covers(zone["id"], user.get("location", [0, 0]))
    return clearing.inside(user.get("location", [0, 0]), zone["polygon"])


def clear_pool(tx, user, pool):
    seller_access(user, pool["seller_id"])
    if pool["status"] not in {"ACCUMULATING", "FAILED"}:
        raise HTTPException(409, "Only accumulating or infeasible pools can be cleared")
    requests = [must(tx, "requests", key) for key in pool["request_ids"]]
    requests = [r for r in requests if r["status"] == "ACTIVE"]
    if not requests:
        raise HTTPException(409, "No active requests in this delivery pool")
    zone = must(tx, "zones", pool["zone_id"])
    products = {p["id"]: p for p in tx.all("products")}
    for buying_request in requests:
        for sku, specification in buying_request.get(
            "approved_product_specifications", {}
        ).items():
            if product_specification(products[sku]) != specification:
                raise HTTPException(
                    409,
                    "Catalog specifications changed after this request; the buyer must review and submit a new request",
                )
    users = {u["id"]: u for u in tx.all("users")}
    result = clearing.solve(
        requests, zone, products, users, available_stock(tx, pool["id"])
    )
    pool["version"] += 1
    pool["updated_at"] = now()
    if result is None:
        pool.update(
            status="FAILED",
            allocations=[],
            reason="No manifest satisfies stock, route capacity, minimum route weight and every buyer's delivered-price ceiling",
        )
    else:
        for allocation in result["allocations"]:
            allocation["product_snapshot"] = product_specification(
                products[allocation["product_id"]]
            )
        pool.update(result)
        pool["status"] = "CLEARED"
        pool["reason"] = (
            "Independent price, stock and freight checks passed. Each buyer must now approve this exact version."
        )
        pool["route"] = clearing.route_order(zone["depot"], pool["allocations"], users)
        snapshot = {
            "pool": pool["id"],
            "version": pool["version"],
            "allocations": pool["allocations"],
            "date": pool["dispatch_date"],
        }
        pool["agreement_hash"] = sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        for a in pool["allocations"]:
            a["order_id"] = str(
                uuid5(
                    NAMESPACE_URL, f"{pool['id']}:{pool['version']}:{a['request_id']}"
                )
            )
    tx.put("pools", pool)
    tx.audit(
        user["id"],
        "POOL_" + pool["status"],
        pool["id"],
        {"version": pool["version"], "included": len(pool["allocations"])},
    )
    return pool


def approve(tx, user, pool, version):
    require_role(user, "RETAILER")
    if pool["status"] != "CLEARED" or pool["version"] != version:
        raise HTTPException(
            409, "This quote is stale or unavailable; review the current pool"
        )
    a = next((a for a in pool["allocations"] if a["buyer_id"] == user["id"]), None)
    if not a:
        raise HTTPException(403, "You have no cleared allocation in this pool")
    existing = tx.get("orders", a["order_id"])
    if existing:
        return existing
    if a["total_minor"] > a["quantity"] * a["ceiling_minor"]:
        raise HTTPException(409, "Price-ceiling validation failed")
    order = tx.put(
        "orders",
        {
            **a,
            "id": a["order_id"],
            "pool_id": pool["id"],
            "pool_version": version,
            "agreement_hash": pool["agreement_hash"],
            "seller_id": pool["seller_id"],
            "status": "APPROVED",
            "payment_status": "NOT_STARTED",
            "refunded_minor": 0,
            "approved_at": now(),
        },
    )
    tx.audit(
        user["id"],
        "ALLOCATION_APPROVED",
        order["id"],
        {"agreement_hash": pool["agreement_hash"]},
    )
    return order


def payment_action(tx, user, order, payments, action):
    order_access(tx, user, order)
    pool = must(tx, "pools", order["pool_id"])
    if action in {"checkout", "authorize"}:
        if user["id"] != order["buyer_id"]:
            raise HTTPException(403, "Only the buyer can approve payment")
        if (
            pool["status"] != "CLEARED"
            or pool["agreement_hash"] != order["agreement_hash"]
        ):
            raise HTTPException(409, "The approved allocation is no longer valid")
    status = order["payment_status"]
    if action == "checkout" and status not in {"NOT_STARTED", "CREATED"}:
        if status == "AUTHORIZED":
            return order
        raise HTTPException(
            409, "Payment has already progressed; reconcile its current state"
        )
    if action == "authorize" and status == "AUTHORIZED":
        return order
    if action == "authorize" and status != "CREATED":
        raise HTTPException(409, "Create a checkout first")
    if action == "capture":
        if status == "CAPTURED":
            return order
        require_role(user, "DRIVER", "SELLER", "ADMIN")
        if (
            not order.get("pod")
            or order["pod"].get("exception")
            or order["pod"]["delivered_quantity"] != order["quantity"]
        ):
            raise HTTPException(
                409, "A complete acknowledged delivery is required before capture"
            )
        if status != "AUTHORIZED":
            raise HTTPException(409, "This payment is not authorized")
    if action == "void":
        seller_access(user, order["seller_id"])
        if status == "VOIDED":
            return order
        if status not in {"NOT_STARTED", "CREATED", "AUTHORIZED"}:
            raise HTTPException(
                409, "This payment cannot be voided without reconciliation"
            )
    order["provider"] = payments.mode
    try:
        if action == "checkout":
            if order.get("provider_order_id"):
                return order
            remote = payments.create(order)
            order.update(provider_order_id=remote["id"], payment_status="CREATED")
            order["approval_url"] = next(
                (
                    link["href"]
                    for link in remote.get("links", [])
                    if link["rel"] in {"approve", "payer-action"}
                ),
                None,
            )
        elif action == "authorize":
            remote = payments.authorize(order)
            order.update(
                authorization_id=remote["id"],
                payment_status="AUTHORIZED",
                authorized_at=now(),
            )
        elif action == "capture":
            remote = payments.capture(order)
            order["capture_id"] = remote["id"]
            order["payment_status"] = (
                "CAPTURED" if remote["status"] == "COMPLETED" else "CAPTURE_PENDING"
            )
        elif action == "void":
            if order.get("authorization_id"):
                payments.void(order)
            order.update(payment_status="VOIDED", status="CANCELLED")
        order.pop("payment_error", None)
    except PaymentError as error:
        order["payment_status"] = "REQUIRES_RECONCILIATION"
        order["payment_error"] = str(error)
        order["uncertain_action"] = action
    tx.put("orders", order)
    tx.audit(
        user["id"],
        "PAYMENT_" + action.upper(),
        order["id"],
        {"state": order["payment_status"], "provider": payments.mode},
    )
    return order


def reconcile(tx, order, payments):
    if payments.mode == "demo":
        return order
    if not order.get("provider_order_id"):
        # Repeating create with the same PayPal-Request-Id resolves uncertain
        # creates without inventing a second external order.
        remote = payments.create(order)
        order["provider_order_id"] = remote["id"]
    remote = payments.call("GET", "/v2/checkout/orders/" + order["provider_order_id"])
    unit = remote["purchase_units"][0]
    from app.platform.payments import amount

    if unit["amount"] != {
        "currency_code": order["currency"],
        "value": amount(order["total_minor"]),
    }:
        raise PaymentError("Remote order does not match this allocation")
    details = unit.get("payments", {})
    captures = details.get("captures", [])
    auths = details.get("authorizations", [])
    if not captures and auths:
        auth = payments.call("GET", "/v2/payments/authorizations/" + auths[0]["id"])
        order["authorization_id"] = auth["id"]
        # Capture IDs may not be embedded in the order after a separate
        # Payments API capture. Follow only the known PayPal capture relation.
        capture_id = order.get("capture_id")
        for link in auth.get("links", []):
            if link.get("rel") == "capture" and "/captures/" in link.get("href", ""):
                capture_id = link["href"].rstrip("/").split("/")[-1]
        if capture_id:
            captures = [payments.call("GET", "/v2/payments/captures/" + capture_id)]
        else:
            order["payment_status"] = {
                "CREATED": "AUTHORIZED",
                "VOIDED": "VOIDED",
                "EXPIRED": "EXPIRED",
            }.get(auth["status"], "REQUIRES_RECONCILIATION")
    if captures:
        capture = captures[0]
        order["capture_id"] = capture["id"]
        order["payment_status"] = {
            "COMPLETED": "CAPTURED",
            "REFUNDED": "REFUNDED",
            "PARTIALLY_REFUNDED": "PARTIALLY_REFUNDED",
            "PENDING": "CAPTURE_PENDING",
        }.get(capture["status"], "REQUIRES_RECONCILIATION")
    elif not auths:
        order["payment_status"] = "CREATED"
    for refund in tx.all("refunds"):
        if (
            refund["order_id"] == order["id"]
            and refund.get("provider_refund_id")
            and refund["status"] != "COMPLETED"
        ):
            remote_refund = payments.call(
                "GET", "/v2/payments/refunds/" + refund["provider_refund_id"]
            )
            refund["status"] = remote_refund["status"]
            tx.put("refunds", refund)
    refunds = [r for r in tx.all("refunds") if r["order_id"] == order["id"]]
    confirmed = sum(r["amount_minor"] for r in refunds if r["status"] == "COMPLETED")
    order["refunded_minor"] = max(order.get("refunded_minor", 0), confirmed)
    if confirmed and order["payment_status"] in {
        "CAPTURED",
        "PARTIALLY_REFUNDED",
        "REFUNDED",
    }:
        order["payment_status"] = (
            "REFUNDED" if confirmed == order["total_minor"] else "PARTIALLY_REFUNDED"
        )
    if any(r["status"] in {"PENDING", "REQUIRES_RECONCILIATION"} for r in refunds):
        order["payment_status"] = "REFUND_PENDING"
    if order["payment_status"] != "REQUIRES_RECONCILIATION":
        order.pop("payment_error", None)
    tx.put("orders", order)
    return order


def cancel_pool(tx, user, pool, payments):
    seller_access(user, pool["seller_id"])
    if pool["status"] == "CANCELLED":
        return pool
    if pool["status"] in {"DISPATCHED", "COMPLETED"}:
        raise HTTPException(
            409, "Dispatched orders require delivery-exception or refund handling"
        )
    orders = [o for o in tx.all("orders") if o["pool_id"] == pool["id"]]
    if any(
        o["payment_status"] not in {"NOT_STARTED", "CREATED", "AUTHORIZED", "VOIDED"}
        for o in orders
    ):
        raise HTTPException(
            409, "Reconcile outstanding payments before cancelling this pool"
        )
    for order in orders:
        payment_action(tx, user, order, payments, "void")
    pending = any(
        must(tx, "orders", o["id"])["payment_status"] != "VOIDED" for o in orders
    )
    pool["status"] = "CANCEL_PENDING" if pending else "CANCELLED"
    tx.put("pools", pool)
    tx.audit(
        user["id"],
        "POOL_CANCELLED" if not pending else "POOL_CANCEL_PENDING",
        pool["id"],
    )
    return pool


def dispatch(tx, user, pool, driver_id):
    seller_access(user, pool["seller_id"])
    if pool["status"] != "CLEARED":
        raise HTTPException(409, "Only a cleared delivery pool can be dispatched")
    driver = must(tx, "users", driver_id)
    if "DRIVER" not in driver["roles"] or not driver.get("active", True):
        raise HTTPException(422, "Assign an active driver")
    orders = [tx.get("orders", a["order_id"]) for a in pool["allocations"]]
    if any(
        not o
        or o["payment_status"] != "AUTHORIZED"
        or o["agreement_hash"] != pool["agreement_hash"]
        for o in orders
    ):
        raise HTTPException(
            409,
            "Every included buyer must approve and authorize the current allocation before dispatch",
        )
    pool.update(status="DISPATCHED", driver_id=driver_id, dispatched_at=now())
    for order in orders:
        order["status"] = "FULFILLING"
        tx.put("orders", order)
    tx.put("pools", pool)
    tx.audit(user["id"], "POOL_DISPATCHED", pool["id"], {"driver_id": driver_id})
    return pool


def delivery(tx, user, order, data, payments):
    require_role(user, "DRIVER")
    pool = must(tx, "pools", order["pool_id"])
    if pool.get("driver_id") != user["id"]:
        raise HTTPException(403, "This route is not assigned to you")
    if order.get("pod"):
        if all(order["pod"].get(k) == v for k, v in data.items()):
            return order
        raise HTTPException(
            409,
            "Delivery evidence is append-only; an existing POD cannot be overwritten",
        )
    if pool["status"] != "DISPATCHED":
        raise HTTPException(409, "This route is not dispatched")
    if data["delivered_quantity"] > order["quantity"]:
        raise HTTPException(422, "Delivered quantity exceeds the order")
    complete = (
        data["delivered_quantity"] == order["quantity"]
        and data["acknowledgement"]
        and not data["exception"]
    )
    if not complete and not data["exception"]:
        raise HTTPException(
            422, "Incomplete or unacknowledged delivery requires an exception"
        )
    order["pod"] = {**data, "recorded_at": now(), "driver_id": user["id"]}
    order["status"] = "DELIVERED" if complete else "DELIVERY_EXCEPTION"
    tx.put("orders", order)
    tx.audit(user["id"], "POD_RECORDED", order["id"], data)
    if complete:
        order = payment_action(tx, user, order, payments, "capture")
    if all(
        (tx.get("orders", a["order_id"]) or {}).get("status")
        in {"DELIVERED", "DELIVERY_EXCEPTION"}
        for a in pool["allocations"]
    ):
        pool["status"] = "COMPLETED"
        tx.put("pools", pool)
        # Move physical inventory only once, after the run is complete. Before
        # then its cleared allocations remain reserved by available_stock().
        for sku, qty in pool["demand"].items():
            item = must(tx, "products", sku)
            item["stock"] -= qty
            tx.put("products", item)
    return order


def smart_receipt(order):
    matched = (
        order.get("pod")
        and not order["pod"].get("exception")
        and order["payment_status"] == "CAPTURED"
    )
    return {
        "issuer": "PayPool",
        "id": "RECEIPT-" + order["id"],
        "status": "MATCHED"
        if matched
        else "REVIEW_REQUIRED"
        if order.get("pod")
        else "PENDING",
        "order": order,
        "generated_at": now(),
        "note": "PayPool reconciliation record; not a PayPal-issued or statutory tax invoice",
    }
