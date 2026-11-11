import json
from datetime import UTC, date, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid4, uuid5
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.platform import clearing
from app.platform.auth import require_role
from app.platform.payments import PaymentError
from app.platform.schedules import approval_deadline, cutoff_for, cutoff_passed
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
        if pool.get("stock_committed"):
            continue
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
    if not item.get("active", True) or not zone.get("active", True):
        raise HTTPException(422, "The product or delivery area is inactive")
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
    if (
        date.fromisoformat(data["dispatch_date"])
        < datetime.now(ZoneInfo(zone.get("timezone", "Asia/Kolkata"))).date()
    ):
        raise HTTPException(422, "Delivery date is in the past")
    if date.fromisoformat(data["dispatch_date"]).weekday() not in zone.get(
        "weekdays", list(range(7))
    ):
        raise HTTPException(
            422, "This distributor does not run this zone on that weekday"
        )
    cutoff = cutoff_for(zone, data["dispatch_date"])
    if cutoff_passed({"cutoff_at": cutoff}):
        raise HTTPException(409, "The buying cutoff for this delivery run has passed")
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
        if item.get("pack", "") != alt.get("pack", ""):
            raise HTTPException(
                422, "A substitute must preserve the approved pack size"
            )
        for attr in (
            set(item.get("attributes", {})) | set(alt.get("attributes", {}))
        ) - {"brand"}:
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
            "cutoff_at": cutoff,
            "delivery_window": zone.get("delivery_window", "09:00–18:00"),
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
    if pool["status"] not in {"ACCUMULATING", "FAILED", "LOCKED"}:
        raise HTTPException(409, "Only accumulating or infeasible pools can be cleared")
    requests = [must(tx, "requests", key) for key in pool["request_ids"]]
    requests = [r for r in requests if r["status"] == "ACTIVE"]
    if not requests:
        raise HTTPException(409, "No active requests in this delivery pool")
    zone = must(tx, "zones", pool["zone_id"])
    if pool["status"] != "LOCKED":
        pool["status"] = "LOCKED"
        pool["locked_at"] = now()
        tx.put("pools", pool)
        tx.audit(user["id"], "POOL_LOCKED", pool["id"])
    pool["status"] = "OPTIMIZING"
    tx.put("pools", pool)
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
        if buying_request.get("accepted_offer_id"):
            offer = must(tx, "offers", buying_request["accepted_offer_id"])

            if offer["status"] != "ACCEPTED" or datetime.fromisoformat(
                offer["expires_at"]
            ) <= datetime.now(UTC):
                raise HTTPException(
                    409,
                    "An accepted offer expired; obtain fresh agreement before clearing",
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
        pool["approval_expires_at"] = approval_deadline(zone, pool["dispatch_date"])
        if datetime.fromisoformat(pool["approval_expires_at"]) <= datetime.now(UTC):
            raise HTTPException(
                409, "The agreed delivery day passed; request fresh buyer requirements"
            )
        for allocation in result["allocations"]:
            allocation["product_snapshot"] = product_specification(
                products[allocation["product_id"]]
            )
            allocation["delivery_location"] = list(
                users[allocation["buyer_id"]]["location"]
            )
            allocation["buyer_name"] = users[allocation["buyer_id"]]["name"]
            allocation["seller_name"] = users[pool["seller_id"]]["name"]
            allocation["recipient_confirmation_required"] = zone.get(
                "recipient_confirmation_required", False
            )
        pool.update(result)
        pool["status"] = "CLEARED"
        pool["reason"] = (
            "Independent price, stock and freight checks passed. Each buyer must now approve this exact version."
        )
        pool["route"] = clearing.route_order(zone["depot"], pool["allocations"], users)
        for a in pool["allocations"]:
            a["order_id"] = str(
                uuid5(
                    NAMESPACE_URL, f"{pool['id']}:{pool['version']}:{a['request_id']}"
                )
            )
        pool["zone_snapshot"] = dict(zone)
        snapshot = {
            "pool": pool["id"],
            "version": pool["version"],
            "allocations": pool["allocations"],
            "date": pool["dispatch_date"],
            "delivery_window": pool.get(
                "delivery_window", zone.get("delivery_window", "09:00–18:00")
            ),
            "approval_expires_at": pool["approval_expires_at"],
            "zone": pool["zone_snapshot"],
        }
        pool["agreement_hash"] = sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    tx.put("pools", pool)
    tx.put(
        "allocation_snapshots",
        {
            "id": f"{pool['id']}:{pool['version']}",
            "pool_id": pool["id"],
            "version": pool["version"],
            "snapshot": dict(pool),
            "created_at": now(),
        },
    )
    tx.audit(
        user["id"],
        "POOL_" + pool["status"],
        pool["id"],
        {"version": pool["version"], "included": len(pool["allocations"])},
    )
    return pool


def approve(tx, user, pool, version):
    require_role(user, "RETAILER")
    if pool.get("approval_expires_at") and datetime.fromisoformat(
        pool["approval_expires_at"]
    ) <= datetime.now(UTC):
        raise HTTPException(409, "This final quote expired; request a fresh agreement")
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


def payment_action(tx, user, order, payments, action, settling_operation=False):
    order_access(tx, user, order)
    if order.get("payment_operation_id") and not settling_operation:
        raise HTTPException(
            409, "A payment operation is in progress; reconcile before continuing"
        )
    pool = must(tx, "pools", order["pool_id"])
    if action in {"checkout", "authorize"}:
        if (
            not settling_operation
            and pool.get("approval_expires_at")
            and datetime.fromisoformat(pool["approval_expires_at"]) <= datetime.now(UTC)
        ):
            raise HTTPException(
                409, "The approved quote expired; reconcile and obtain fresh agreement"
            )
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
        if not (user["id"] == order["buyer_id"] and order.get("buyer_confirmed_at")):
            require_role(user, "DRIVER", "SELLER", "ADMIN")
        if (
            order.get("recipient_confirmation_required") or payments.mode != "demo"
        ) and not order.get("buyer_confirmed_at"):
            raise HTTPException(409, "The buyer must confirm receipt before capture")
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
            if not isinstance(remote.get("id"), str) or not remote["id"]:
                raise PaymentError(
                    "Provider order reference is missing; reconcile before continuing"
                )
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
            if not isinstance(remote.get("id"), str) or not remote["id"]:
                raise PaymentError(
                    "Provider authorization reference is missing; reconcile before continuing"
                )
            order.update(
                authorization_id=remote["id"],
                payment_status="AUTHORIZED",
                authorized_at=now(),
            )
        elif action == "capture":
            remote = payments.capture(order)
            if not isinstance(remote.get("id"), str) or not remote["id"]:
                raise PaymentError(
                    "Provider capture reference is missing; reconcile before continuing"
                )
            if payments.mode != "demo":
                from app.platform.payments import amount

                if remote.get("amount") != {
                    "currency_code": order["currency"],
                    "value": amount(order["total_minor"]),
                }:
                    raise PaymentError(
                        "Capture amount does not match the approved allocation"
                    )
            order["capture_id"] = remote["id"]
            order["payment_status"] = (
                "CAPTURED" if remote["status"] == "COMPLETED" else "CAPTURE_PENDING"
            )
        elif action == "void":
            if order.get("authorization_id"):
                payments.void(order)
            order.update(payment_status="VOIDED", status="CANCELLED")
        order.pop("payment_error", None)
    except (PaymentError, KeyError, TypeError) as error:
        order["payment_status"] = "REQUIRES_RECONCILIATION"
        order["payment_error"] = (
            str(error)
            if isinstance(error, PaymentError)
            else "Provider response lacked required fields; reconcile before continuing"
        )
        order["uncertain_action"] = action
    tx.put("orders", order)
    tx.audit(
        user["id"],
        "PAYMENT_" + action.upper(),
        order["id"],
        {
            "state": order["payment_status"],
            "provider": payments.mode,
            "amount_minor": order["total_minor"],
        },
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
    if len(remote.get("purchase_units", [])) != 1 or (
        remote.get("id") and remote["id"] != order["provider_order_id"]
    ):
        raise PaymentError("Remote order identity does not match this allocation")
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
        if auth.get("status") in {"CREATED", "AUTHORIZED"} and auth.get("amount") != {
            "currency_code": order["currency"],
            "value": amount(order["total_minor"]),
        }:
            raise PaymentError(
                "Authorized amount does not match the buyer-approved total"
            )
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
        confirmed_captures = [
            c
            for c in captures
            if c.get("status") in {"COMPLETED", "PARTIALLY_REFUNDED", "REFUNDED"}
        ]
        if len(confirmed_captures) > 1:
            raise PaymentError(
                "Multiple captures require explicit reconciliation; automatic matching is disabled"
            )
        capture = confirmed_captures[0] if confirmed_captures else captures[0]
        if not isinstance(capture.get("id"), str) or not capture["id"]:
            raise PaymentError("Capture reference is missing")
        if capture.get("amount") != {
            "currency_code": order["currency"],
            "value": amount(order["total_minor"]),
        }:
            raise PaymentError(
                "Captured amount differs from the approved full-order total"
            )
        order["capture_id"] = capture["id"]
        order["payment_status"] = {
            "COMPLETED": "CAPTURED",
            "REFUNDED": "REFUNDED",
            "PARTIALLY_REFUNDED": "PARTIALLY_REFUNDED",
            "PENDING": "CAPTURE_PENDING",
        }.get(capture["status"], "REQUIRES_RECONCILIATION")
        if capture["status"] == "REFUNDED":
            order["refunded_minor"] = order["total_minor"]
    elif not auths:
        order["payment_status"] = (
            "CREATED"
            if remote.get("status")
            in {"CREATED", "SAVED", "APPROVED", "PAYER_ACTION_REQUIRED"}
            else "VOIDED"
            if remote.get("status") == "VOIDED"
            else "REQUIRES_RECONCILIATION"
        )
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
    if (
        confirmed
        and order["refunded_minor"] < order["total_minor"]
        and order["payment_status"]
        in {
            "CAPTURED",
            "PARTIALLY_REFUNDED",
            "REFUNDED",
        }
    ):
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
        o.get("payment_operation_id")
        or o["payment_status"] not in {"NOT_STARTED", "CREATED", "AUTHORIZED", "VOIDED"}
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


def dispatch(tx, user, pool, driver_id, vehicle_id=None):
    seller_access(user, pool["seller_id"])
    if pool["status"] != "CLEARED":
        raise HTTPException(409, "Only a cleared delivery pool can be dispatched")
    driver = must(tx, "users", driver_id)
    if any(
        p["id"] != pool["id"]
        and p["status"] == "DISPATCHED"
        and p.get("driver_id") == driver_id
        for p in tx.all("pools")
    ):
        raise HTTPException(409, "This driver is already completing another route")
    if vehicle_id:
        vehicle = must(tx, "vehicles", vehicle_id)
        if vehicle["seller_id"] != pool["seller_id"] or not vehicle["active"]:
            raise HTTPException(
                422, "Choose an active vehicle belonging to this distributor"
            )
        if (
            pool["weight_grams"] > vehicle["max_weight_grams"]
            or pool["volume_cm3"] > vehicle["max_volume_cm3"]
        ):
            raise HTTPException(409, "The cleared load exceeds this vehicle's capacity")
        if any(
            p["id"] != pool["id"]
            and p["status"] == "DISPATCHED"
            and p.get("vehicle_id") == vehicle_id
            for p in tx.all("pools")
        ):
            raise HTTPException(
                409, "This vehicle is already assigned to an active route"
            )
        pool.update(vehicle_id=vehicle_id, vehicle_snapshot=vehicle)
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
    if not pool.get("stock_committed"):
        for sku, quantity in pool["demand"].items():
            item = must(tx, "products", sku)
            if item["stock"] < quantity:
                raise HTTPException(409, "Inventory changed before dispatch")
            item["stock"] -= quantity
            item["stock_updated_at"] = now()
            tx.put("products", item)
            tx.put(
                "stock_movements",
                {
                    "id": f"dispatch:{pool['id']}:{sku}",
                    "seller_id": pool["seller_id"],
                    "product_id": sku,
                    "delta": -quantity,
                    "balance": item["stock"],
                    "reason": "Dispatched locked allocation",
                    "actor": user["id"],
                    "at": now(),
                },
            )
        pool["stock_committed"] = True
    for order in orders:
        order["status"] = "FULFILLING"
        tx.put("orders", order)
    tx.put("pools", pool)
    tx.audit(user["id"], "POOL_DISPATCHED", pool["id"], {"driver_id": driver_id})
    return pool


def delivery(tx, user, order, data, payments, defer_capture=False):
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
    confirmation_required = (
        order.get("recipient_confirmation_required") or payments.mode != "demo"
    )
    order["recipient_confirmation_required"] = confirmation_required
    order["status"] = (
        ("AWAITING_CONFIRMATION" if confirmation_required else "DELIVERED")
        if complete
        else "DELIVERY_EXCEPTION"
    )
    tx.put("orders", order)
    tx.audit(user["id"], "POD_RECORDED", order["id"], data)
    if complete and not confirmation_required:
        if defer_capture:
            order["capture_requested"] = True
            tx.put("orders", order)
        else:
            order = payment_action(tx, user, order, payments, "capture")
    if all(
        (tx.get("orders", a["order_id"]) or {}).get("status")
        in {"DELIVERED", "DELIVERY_EXCEPTION", "AWAITING_CONFIRMATION", "CANCELLED"}
        for a in pool["allocations"]
    ):
        pool["status"] = "COMPLETED"
        tx.put("pools", pool)
        # Move physical inventory only once, after the run is complete. Before
        # then its cleared allocations remain reserved by available_stock().
        if not pool.get("stock_committed"):
            for sku, qty in pool["demand"].items():
                item = must(tx, "products", sku)
                item["stock"] -= qty
                tx.put("products", item)
            pool["stock_committed"] = True
            tx.put("pools", pool)
    return order


def smart_receipt(order):
    matched = (
        order.get("pod")
        and not order["pod"].get("exception")
        and order["payment_status"] == "CAPTURED"
        and (
            not order.get("recipient_confirmation_required")
            or bool(order.get("buyer_confirmed_at"))
        )
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
        "note": "PayPool reconciliation record; not a PayPal-issued or statutory tax invoice"
        + (
            ". SIMULATED PAYMENTS: no money moved"
            if order.get("provider") == "demo"
            else ""
        ),
    }
