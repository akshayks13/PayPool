import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from html import escape
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.platform import commercial, payment_execution, service
from app.platform.auth import current_user, require_role, store_for
from app.platform.models import (
    AgentAccess,
    CounterOffer,
    ExceptionResolution,
    InventoryChange,
    NewOffer,
    StandingOrder,
    StateChange,
    Vehicle,
    Version,
    Zone,
)
from app.platform.store import now

router = APIRouter(prefix="/api/v1", tags=["commerce operations"])


@router.get("/seller/product-feed")
def product_feed(user=Depends(current_user), store=Depends(store_for)):
    require_role(user, "SELLER")
    from app.platform.feed import prepare

    with store.transaction() as tx:
        return prepare(tx, user)


@router.post("/seller/product-feed/preview")
def preview_feed(user=Depends(current_user), store=Depends(store_for)):
    require_role(user, "SELLER")
    from app.platform.feed import prepare

    with store.transaction() as tx:
        report = prepare(tx, user)
        run = tx.put(
            "acp_product_feed_runs",
            {
                "id": str(uuid4()),
                "seller_id": user["id"],
                "at": now(),
                "valid_count": len(report["products"]),
                "rejected_count": len(report["rejected"]),
                "published": False,
                "specification": report["source"],
            },
        )
        tx.audit(
            user["id"],
            "PRODUCT_FEED_PREPARED",
            run["id"],
            {
                "valid_count": run["valid_count"],
                "rejected_count": run["rejected_count"],
            },
        )
        return {**report, "run_id": run["id"]}


def close_exception(store, user, order_id, data, payments):
    terms = data.model_dump()
    with store.transaction() as tx:
        order = service.must(tx, "orders", order_id)
        service.seller_access(user, order["seller_id"])
        if order.get("exception_resolution"):
            if order["exception_resolution"]["terms"] != terms:
                raise HTTPException(
                    409, "This exception was already resolved with different terms"
                )
            return order
        if order["status"] != "DELIVERY_EXCEPTION" and not (
            order["payment_status"] == "VOIDED"
            and (order.get("pod") or {}).get("exception")
        ):
            raise HTTPException(409, "Only an unresolved exception can be closed")
        if data.returned_quantity > order["quantity"] or data.replacement_quantity:
            raise HTTPException(
                422,
                "Validate returned units; a closed order cannot dispatch replacements",
            )
        if (
            order.get("pending_exception_resolution")
            and order["pending_exception_resolution"] != terms
        ):
            raise HTTPException(
                409, "This cancellation is already pending with different terms"
            )
        order["pending_exception_resolution"] = terms
        tx.put("orders", order)
    result = payment_execution.execute(store, user, order_id, payments, "void")
    if result["payment_status"] != "VOIDED":
        return result
    with store.transaction() as tx:
        order = service.must(tx, "orders", order_id)
        if order.get("exception_resolution"):
            return order
        if data.returned_quantity:
            item = service.must(tx, "products", order["product_id"])
            item["stock"] += data.returned_quantity
            item["stock_updated_at"] = now()
            tx.put("products", item)
            tx.put(
                "stock_movements",
                {
                    "id": f"exception-return:{order_id}",
                    "product_id": item["id"],
                    "seller_id": order["seller_id"],
                    "delta": data.returned_quantity,
                    "balance": item["stock"],
                    "reason": data.reason,
                    "actor": user["id"],
                    "at": now(),
                },
            )
        order.update(
            status="CANCELLED",
            exception_resolution={
                "terms": terms,
                "resolved_at": now(),
                "actor": user["id"],
            },
        )
        order.pop("pending_exception_resolution", None)
        tx.put("orders", order)
        tx.audit(user["id"], "DELIVERY_EXCEPTION_RESOLVED", order_id, terms)
        return order


@router.post("/me/agent-access")
def create_agent_access(
    data: AgentAccess, user=Depends(current_user), store=Depends(store_for)
):
    require_role(user, "RETAILER")
    token = secrets.token_urlsafe(40)
    with store.transaction() as tx:
        record = tx.put(
            "agent_access",
            {
                "id": hashlib.sha256(token.encode()).hexdigest(),
                "client_id": str(uuid4()),
                "buyer_id": user["id"],
                "name": data.name,
                "active": True,
                "created_at": now(),
                "expires_at": (
                    datetime.now(UTC) + timedelta(hours=data.expires_in_hours)
                ).isoformat(),
            },
        )
        tx.audit(
            user["id"],
            "AGENT_ACCESS_GRANTED",
            record["client_id"],
            {
                "scope": "Read buyer-approved quotes and create continuation sessions; no purchase approval or payment authority"
            },
        )
        return {
            "client_id": record["client_id"],
            "name": record["name"],
            "expires_at": record["expires_at"],
            "token": token,
            "warning": "Shown once. This token cannot approve purchases or move money.",
        }


@router.post("/me/agent-access/{client_id}/revoke")
def revoke_agent_access(
    client_id: str, user=Depends(current_user), store=Depends(store_for)
):
    with store.transaction() as tx:
        record = next(
            (
                r
                for r in tx.all("agent_access")
                if r["client_id"] == client_id and r["buyer_id"] == user["id"]
            ),
            None,
        )
        if not record:
            raise HTTPException(404, "Agent access not found")
        record["active"] = False
        tx.put("agent_access", record)
        tx.audit(user["id"], "AGENT_ACCESS_REVOKED", client_id)
        return {"revoked": True}


@router.get("/admin/operations")
def operations(user=Depends(current_user), store=Depends(store_for)):
    require_role(user, "ADMIN")
    with store.transaction() as tx:
        orders = tx.all("orders")
        return {
            "worker": tx.get("worker_health", "commerce-worker"),
            "queue": {
                state: sum(e["status"] == state for e in tx.all("outbox"))
                for state in ("PENDING", "RETRY", "DEAD_LETTER", "DELIVERED")
            },
            "payment_states": {
                state: sum(o["payment_status"] == state for o in orders)
                for state in sorted({o["payment_status"] for o in orders})
            },
            "ledger": sorted(
                tx.all("payment_ledger"), key=lambda r: r["at"], reverse=True
            )[:100],
            "capabilities": {
                "paypal_sandbox_credentials": bool(
                    os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_CLIENT_SECRET")
                ),
                "webhook_verification": bool(os.getenv("PAYPAL_WEBHOOK_ID")),
                "gemini": bool(os.getenv("GEMINI_API_KEY")),
                "acp_api_enabled": os.getenv("ACP_ENABLED", "false") == "true",
                "delegated_payments": False,
                "vault": False,
                "multiparty_onboarding": False,
                "search": bool(os.getenv("ELASTICSEARCH_URL")),
            },
        }


@router.post("/admin/jobs/{event_id}/retry")
def retry(event_id: str, user=Depends(current_user), store=Depends(store_for)):
    require_role(user, "ADMIN")
    with store.transaction() as tx:
        record = service.must(tx, "outbox", event_id)
        if record["status"] == "DELIVERED":
            raise HTTPException(409, "This event was already delivered")
        record.update(status="PENDING", next_attempt_at=now(), attempts=0)
        tx.put("outbox", record)
        tx.audit(user["id"], "OUTBOX_RETRY_REQUESTED", event_id)
        return record


@router.post("/admin/worker/tick")
def run_worker(request: Request, user=Depends(current_user), store=Depends(store_for)):
    require_role(user, "ADMIN")
    from app.platform.worker import tick

    return tick(store, request.app.state.payments)


@router.get("/seller/yield-advice")
def yield_advice(user=Depends(current_user), store=Depends(store_for)):
    require_role(user, "SELLER", "ADMIN")
    with store.transaction() as tx:
        advice = []
        for zone in tx.all("zones"):
            if "ADMIN" not in user["roles"] and zone["seller_id"] != user["id"]:
                continue
            completed = [
                p
                for p in tx.all("pools")
                if p["zone_id"] == zone["id"] and p["status"] == "COMPLETED"
            ]
            for pool in tx.all("pools"):
                if pool["zone_id"] != zone["id"] or pool["status"] not in {
                    "ACCUMULATING",
                    "FAILED",
                    "LOCKED",
                }:
                    continue
                requests = [
                    r
                    for r in tx.all("requests")
                    if r["pool_id"] == pool["id"] and r["status"] == "ACTIVE"
                ]
                weight = sum(
                    service.must(tx, "products", r["product_id"])["weight_grams"]
                    * r["quantity_min"]
                    for r in requests
                )
                advice.append(
                    {
                        "pool_id": pool["id"],
                        "zone": zone["name"],
                        "current_weight_grams": weight,
                        "minimum_weight_gap": max(0, zone["min_weight_grams"] - weight),
                        "capacity_utilization_percent": round(
                            100 * weight / zone["max_weight_grams"], 1
                        ),
                        "observed_completed_runs": len(completed),
                        "historical_mean_weight_grams": round(
                            sum(p.get("weight_grams", 0) for p in completed)
                            / len(completed)
                        )
                        if completed
                        else None,
                        "recommendation": "Collect more compatible demand"
                        if weight < zone["min_weight_grams"]
                        else "Ready to evaluate a final quote",
                        "basis": "Recorded demand and completed runs; no external seasonality forecast or automatic price change",
                    }
                )
        return advice


@router.get("/me/roles")
def roles(user=Depends(current_user)):
    return {"roles": user["roles"]}


@router.get("/orders/{order_id}/receipt.html", response_class=HTMLResponse)
def printable_receipt(
    order_id: str, user=Depends(current_user), store=Depends(store_for)
):
    with store.transaction() as tx:
        order = service.must(tx, "orders", order_id)
        service.order_access(tx, user, order)
        receipt = service.smart_receipt(order)
        buyer, seller = (
            service.must(tx, "users", order["buyer_id"]),
            service.must(tx, "users", order["seller_id"]),
        )
        product = order.get("product_snapshot", {})

        def safe(value):
            return escape(str(value))

        def cash(value):
            return f"{safe(order['currency'])} {value // 100:,}.{value % 100:02d}"

        events = [e for e in tx.all("payment_events") if e.get("order_id") == order_id]
        pod = order.get("pod") or {}
        html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PayPool receipt {safe(order_id)}</title><style>body{{font:15px/1.6 system-ui,sans-serif;color:#172033;margin:40px auto;max-width:850px;padding:0 20px}}h1{{font-size:30px}}header{{border-bottom:3px solid #2563eb}}table{{border-collapse:collapse;width:100%;margin:24px 0}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #ddd}}small,.muted{{color:#526079}}code{{overflow-wrap:anywhere}}.status{{background:#eff6ff;padding:12px}}@media print{{body{{margin:0;max-width:none}}}}</style></head><body><header><h1>PayPool Smart Receipt</h1><p>Receipt {safe(receipt["id"])}</p></header><p class="status"><strong>{safe(receipt["status"])}</strong> · {safe(order["payment_status"])}</p><p><strong>Buyer:</strong> {safe(buyer["name"])}<br><strong>Distributor:</strong> {safe(seller["name"])}<br><strong>Approved:</strong> {safe(order.get("approved_at", ""))}</p><table><thead><tr><th>Approved item</th><th>Quantity</th><th>Unit price</th><th>Goods total</th></tr></thead><tbody><tr><td>{safe(product.get("title", order["product_id"]))}<br><small>{safe(product.get("attributes", {}))}</small></td><td>{order["quantity"]} {safe(product.get("unit", "units"))}</td><td>{cash(order["unit_price_minor"])}</td><td>{cash(order["quantity"] * order["unit_price_minor"])}</td></tr></tbody></table><p>Shared freight: <strong>{cash(order["freight_minor"])}</strong><br>Agreed total: <strong>{cash(order["total_minor"])}</strong><br>Refunded: {cash(order.get("refunded_minor", 0))}<br>Delivered-price limit: {cash(order["ceiling_minor"])} / {safe(product.get("unit", "unit"))}</p><h2>Reconciliation evidence</h2><p>Delivered: {safe(pod.get("delivered_quantity", "Pending"))} units<br>Recipient: {safe(pod.get("recipient_name", "Pending"))}<br>Delivery exception: {safe(pod.get("exception") or "None recorded")}<br>Buyer confirmation: {safe(order.get("buyer_confirmed_at", "Not recorded / not required in this demo policy"))}<br>Capture reference: …{safe(order.get("capture_id", "pending")[-8:])}<br>Signature-verified provider events: {len(events)}</p><p>Agreement version {safe(order["pool_version"])}<br><code>{safe(order["agreement_hash"])}</code></p><p class="muted">Seller unit prices include applicable tax. Freight is disclosed separately. {safe(receipt["note"])}. Use your browser's Print command to save or print this record.</p></body></html>"""
        return HTMLResponse(
            html,
            headers={
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )


@router.get("/offers")
def offers(
    request_id: str | None = None, user=Depends(current_user), store=Depends(store_for)
):
    with store.transaction() as tx:
        return [
            o
            for o in tx.all("offers")
            if (
                "ADMIN" in user["roles"]
                or user["id"] in {o["buyer_id"], o["seller_id"]}
            )
            and (request_id is None or o["request_id"] == request_id)
        ]


@router.get("/offers/{offer_id}")
def offer(offer_id: str, user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        record = service.must(tx, "offers", offer_id)
        commercial.access(user, record)
        return {
            **record,
            "revisions": [
                r for r in tx.all("offer_revisions") if r["offer_id"] == offer_id
            ],
        }


@router.post("/offers")
def new_offer(
    data: NewOffer,
    request: Request,
    user=Depends(current_user),
    store=Depends(store_for),
):
    key = request.headers.get("Idempotency-Key", "")
    if len(key) < 8 or len(key) > 100:
        raise HTTPException(422, "Provide an Idempotency-Key of 8–100 characters")
    identity = hashlib.sha256(f"{user['id']}:{key}".encode()).hexdigest()
    with store.transaction() as tx:
        previous = tx.get("offer_operations", identity)
        payload = data.model_dump(mode="json")
        if previous:
            if previous["payload"] != payload:
                raise HTTPException(409, "This key is bound to other offer terms")
            return service.must(tx, "offers", previous["offer_id"])
        result = commercial.propose(tx, user, payload)
        tx.put(
            "offer_operations",
            {"id": identity, "offer_id": result["id"], "payload": payload},
        )
        return result


@router.post("/offers/{offer_id}/counter")
def counter(
    offer_id: str,
    data: CounterOffer,
    user=Depends(current_user),
    store=Depends(store_for),
):
    with store.transaction() as tx:
        previous = service.must(tx, "offers", offer_id)
        commercial.access(user, previous)
        return commercial.propose(tx, user, data.model_dump(mode="json"), previous)


@router.post("/offers/{offer_id}/accept")
def accept(
    offer_id: str, data: Version, user=Depends(current_user), store=Depends(store_for)
):
    with store.transaction() as tx:
        return commercial.accept(
            tx, user, service.must(tx, "offers", offer_id), data.version
        )


@router.post("/procurement/requests/{request_id}/negotiate")
def negotiate(request_id: str, user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        buying = commercial.open_request(tx, user, request_id)
        if user["id"] != buying["buyer_id"]:
            raise HTTPException(403, "Only the buyer starts this procurement agent run")
        item = service.must(tx, "products", buying["product_id"])
        pool = service.must(tx, "pools", buying["pool_id"])
        demand = sum(
            r["quantity_min"]
            for r in tx.all("requests")
            if r["pool_id"] == pool["id"]
            and r["product_id"] == item["id"]
            and r["status"] == "ACTIVE"
        )
        from app.platform.clearing import tier_price

        price = tier_price(item, demand)
        run = {
            "id": str(uuid4()),
            "buyer_id": buying["buyer_id"],
            "seller_id": buying["seller_id"],
            "request_id": request_id,
            "created_at": now(),
            "status": "PROPOSED"
            if price <= buying["ceiling_minor"]
            else "MORE_DEMAND_REQUIRED",
            "tools": [
                {
                    "agent": "BUYER_PROCUREMENT",
                    "tool": "get_confirmed_request",
                    "outcome": "constraints preserved",
                },
                {
                    "agent": "DISTRIBUTOR_YIELD",
                    "tool": "get_price_tiers",
                    "outcome": f"Earned unit price {price}; aggregate {demand}",
                },
            ],
            "proposal": {
                "product_id": item["id"],
                "quantity_min": buying["quantity_min"],
                "quantity_max": buying["quantity_max"],
                "unit_price_minor": price,
                "expires_in_hours": 24,
                "note": "Supplier policy proposal; freight and final pool approval remain required.",
            },
        }
        tx.put("agent_runs", run)
        for index, call in enumerate(run["tools"]):
            tx.put(
                "agent_tool_calls",
                {
                    **call,
                    "id": f"{run['id']}:{index}",
                    "run_id": run["id"],
                    "request_id": request_id,
                    "at": now(),
                },
            )
        tx.audit(user["id"], "AGENT_PROPOSAL_READY", request_id, {"run_id": run["id"]})
        return run


@router.post("/seller/inventory")
def inventory(
    data: InventoryChange, user=Depends(current_user), store=Depends(store_for)
):
    with store.transaction() as tx:
        item = service.must(tx, "products", data.product_id)
        service.seller_access(user, item["seller_id"])
        if item["stock"] != data.expected_stock:
            raise HTTPException(
                409, "Stock changed since this form was opened; refresh and review"
            )
        if service.available_stock(tx).get(item["id"], 0) + data.delta < 0:
            raise HTTPException(409, "Adjustment would consume reserved stock")
        item["stock"] += data.delta
        item["stock_updated_at"] = now()
        tx.put("products", item)
        tx.put(
            "stock_movements",
            {
                "id": str(uuid4()),
                "product_id": item["id"],
                "seller_id": item["seller_id"],
                "delta": data.delta,
                "balance": item["stock"],
                "reason": data.reason,
                "actor": user["id"],
                "at": now(),
            },
        )
        tx.audit(
            user["id"],
            "INVENTORY_STOCK_CHANGED",
            item["id"],
            {"delta": data.delta, "reason": data.reason},
        )
        return item


@router.post("/seller/products/{product_id}/archive")
def archive(
    product_id: str,
    data: StateChange,
    user=Depends(current_user),
    store=Depends(store_for),
):
    with store.transaction() as tx:
        item = service.must(tx, "products", product_id)
        service.seller_access(user, item["seller_id"])
        if item["stock"] != service.available_stock(tx).get(item["id"], 0):
            raise HTTPException(409, "Reserved products cannot be archived")
        item.update(active=data.active, updated_at=now())
        tx.put("products", item)
        tx.audit(user["id"], "PRODUCT_STATUS_CHANGED", item["id"])
        return item


@router.put("/seller/zones/{zone_id}")
def update_zone(
    zone_id: str, data: Zone, user=Depends(current_user), store=Depends(store_for)
):
    with store.transaction() as tx:
        zone = service.must(tx, "zones", zone_id)
        service.seller_access(user, zone["seller_id"])
        if any(
            p["zone_id"] == zone_id and p["status"] not in {"CANCELLED", "COMPLETED"}
            for p in tx.all("pools")
        ):
            raise HTTPException(
                409, "Finish or cancel active pools before changing delivery terms"
            )
        result = tx.put(
            "zones",
            {
                **data.model_dump(mode="json"),
                "id": zone_id,
                "seller_id": zone["seller_id"],
                "updated_at": now(),
            },
        )
        tx.audit(user["id"], "DELIVERY_ZONE_UPDATED", zone_id)
        return result


@router.post("/seller/vehicles")
def vehicle(data: Vehicle, user=Depends(current_user), store=Depends(store_for)):
    require_role(user, "SELLER")
    with store.transaction() as tx:
        if any(
            v["seller_id"] == user["id"]
            and v["registration"].casefold() == data.registration.casefold()
            for v in tx.all("vehicles")
        ):
            raise HTTPException(409, "This vehicle registration already exists")
        result = tx.put(
            "vehicles",
            {
                **data.model_dump(),
                "id": str(uuid4()),
                "seller_id": user["id"],
                "created_at": now(),
            },
        )
        tx.audit(user["id"], "VEHICLE_CREATED", result["id"])
        return result


@router.put("/seller/vehicles/{vehicle_id}")
def update_vehicle(
    vehicle_id: str, data: Vehicle, user=Depends(current_user), store=Depends(store_for)
):
    with store.transaction() as tx:
        existing = service.must(tx, "vehicles", vehicle_id)
        service.seller_access(user, existing["seller_id"])
        if any(
            p.get("vehicle_id") == vehicle_id and p["status"] == "DISPATCHED"
            for p in tx.all("pools")
        ):
            raise HTTPException(409, "This vehicle is assigned to an active route")
        return tx.put(
            "vehicles",
            {
                **data.model_dump(),
                "id": vehicle_id,
                "seller_id": existing["seller_id"],
                "updated_at": now(),
            },
        )


@router.post("/standing-orders")
def standing(data: StandingOrder, user=Depends(current_user), store=Depends(store_for)):
    require_role(user, "RETAILER")
    if data.end_date and data.end_date < data.request.dispatch_date:
        raise HTTPException(422, "End date precedes first delivery")
    with store.transaction() as tx:
        # Reuse submission validation inside a rolled-back savepoint. No order
        # or pool membership is created until the standing instruction is due.
        savepoint = tx.connection.begin_nested()
        try:
            validated = service.submit_request(
                tx, user, data.request.model_dump(mode="json")
            )
            specifications = validated["approved_product_specifications"]
        finally:
            savepoint.rollback()
        record = tx.put(
            "standing_orders",
            {
                **data.model_dump(mode="json"),
                "id": str(uuid4()),
                "buyer_id": user["id"],
                "seller_id": validated["seller_id"],
                "active": True,
                "next_dispatch_date": data.request.dispatch_date.isoformat(),
                "approved_product_specifications": specifications,
                "created_at": now(),
            },
        )
        tx.audit(user["id"], "STANDING_ORDER_CREATED", record["id"])
        return record


@router.post("/standing-orders/{standing_id}/state")
def standing_state(
    standing_id: str,
    data: StateChange,
    user=Depends(current_user),
    store=Depends(store_for),
):
    with store.transaction() as tx:
        record = service.must(tx, "standing_orders", standing_id)
        if record["buyer_id"] != user["id"]:
            raise HTTPException(
                403, "This buying instruction belongs to another retailer"
            )
        record["active"] = data.active
        tx.put("standing_orders", record)
        tx.audit(user["id"], "STANDING_ORDER_STATE_CHANGED", standing_id)
        return record


@router.get("/features")
def features(user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        uid, admin = user["id"], "ADMIN" in user["roles"]

        def visible(r):
            return admin or uid in {r.get("buyer_id"), r.get("seller_id")}

        return {
            "agent_access": [
                {k: r[k] for k in ("client_id", "name", "active", "expires_at")}
                for r in tx.all("agent_access")
                if r["buyer_id"] == uid
            ],
            "offers": [r for r in tx.all("offers") if visible(r)],
            "standing_orders": [
                r for r in tx.all("standing_orders") if r["buyer_id"] == uid
            ],
            "vehicles": [
                r for r in tx.all("vehicles") if admin or r["seller_id"] == uid
            ],
            "stock_movements": [
                r for r in tx.all("stock_movements") if admin or r["seller_id"] == uid
            ][-100:],
            "agent_runs": [r for r in tx.all("agent_runs") if visible(r)][-50:],
            "jobs": tx.all("outbox")[-100:] if admin else [],
        }


@router.post("/orders/{order_id}/confirm-delivery")
def confirm_delivery(
    order_id: str,
    request: Request,
    user=Depends(current_user),
    store=Depends(store_for),
):
    with store.transaction() as tx:
        order = service.must(tx, "orders", order_id)
        if order["buyer_id"] != user["id"]:
            raise HTTPException(403, "Only the purchasing retailer can confirm receipt")
        if (
            not order.get("pod")
            or order["pod"].get("exception")
            or order["pod"]["delivered_quantity"] != order["quantity"]
        ):
            raise HTTPException(409, "Complete delivery evidence is required")
        if order["status"] in {"CANCELLED", "DELIVERY_EXCEPTION"}:
            raise HTTPException(
                409, "Resolve the delivery exception before confirmation"
            )
        if not order.get("buyer_confirmed_at"):
            order.update(buyer_confirmed_at=now(), status="DELIVERED")
            tx.put("orders", order)
            tx.put(
                "delivery_confirmations",
                {
                    "id": order_id,
                    "order_id": order_id,
                    "buyer_id": user["id"],
                    "confirmed_at": order["buyer_confirmed_at"],
                },
            )
            tx.audit(user["id"], "BUYER_RECEIPT_CONFIRMED", order_id)
    return payment_execution.execute(
        store, user, order_id, request.app.state.payments, "capture"
    )


@router.post("/orders/{order_id}/resolve-exception")
def resolve_exception(
    order_id: str,
    data: ExceptionResolution,
    request: Request,
    user=Depends(current_user),
    store=Depends(store_for),
):
    if data.action == "VOID_AND_CLOSE":
        return close_exception(store, user, order_id, data, request.app.state.payments)
    with store.transaction() as tx:
        order = service.must(tx, "orders", order_id)
        service.seller_access(user, order["seller_id"])
        if order.get("pending_exception_resolution"):
            raise HTTPException(
                409, "Finish the pending cancellation before arranging redelivery"
            )
        if order["status"] != "DELIVERY_EXCEPTION":
            raise HTTPException(
                409, "Only an unresolved delivery exception can use this action"
            )
        pool = service.must(tx, "pools", order["pool_id"])
        if (
            data.returned_quantity > order["quantity"]
            or data.replacement_quantity > order["quantity"]
        ):
            raise HTTPException(
                422,
                "Returned and replacement quantities cannot exceed the original order",
            )
        if order["payment_status"] != "AUTHORIZED":
            raise HTTPException(
                409, "Redelivery requires a valid uncaptured authorization"
            )
        if any(
            p["id"] != pool["id"]
            and p["status"] == "DISPATCHED"
            and (
                p.get("driver_id") == pool.get("driver_id")
                or (
                    pool.get("vehicle_id")
                    and p.get("vehicle_id") == pool.get("vehicle_id")
                )
            )
            for p in tx.all("pools")
        ):
            raise HTTPException(
                409, "The assigned driver or vehicle is busy with another run"
            )
        # Every previous attempt remains append-only. The new POD reports
        # cumulative good units received, bounded by the original order.
        history = tx.put(
            "delivery_attempts",
            {
                "id": str(uuid4()),
                "order_id": order_id,
                "pod": order["pod"],
                "resolved_at": now(),
                "reason": data.reason,
            },
        )
        order.setdefault("pod_history", []).append(history)
        order.pop("pod")
        order.pop("buyer_confirmed_at", None)
        order["status"] = "FULFILLING"
        tx.put("orders", order)
        pool["status"] = "DISPATCHED"
        tx.put("pools", pool)
        result = order
        delta = data.returned_quantity - data.replacement_quantity
        if delta:
            item = service.must(tx, "products", order["product_id"])
            if service.available_stock(tx).get(item["id"], 0) + delta < 0:
                raise HTTPException(409, "Insufficient unreserved replacement stock")
            item["stock"] += delta
            item["stock_updated_at"] = now()
            tx.put("products", item)
            tx.put(
                "stock_movements",
                {
                    "id": str(uuid4()),
                    "seller_id": order["seller_id"],
                    "product_id": item["id"],
                    "delta": delta,
                    "balance": item["stock"],
                    "reason": data.reason,
                    "actor": user["id"],
                    "at": now(),
                },
            )
        tx.audit(
            user["id"], "DELIVERY_EXCEPTION_RESOLVED", order_id, {**data.model_dump()}
        )
        return result


@router.get("/catalog/search")
def catalog(
    q: str = "",
    category: str = "",
    seller_id: str = "",
    currency: str = "",
    in_stock: bool = True,
    offset: int = 0,
    limit: int = 30,
    user=Depends(current_user),
    store=Depends(store_for),
):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(422, "Use limit 1–100 and a nonnegative offset")
    from app.platform.router import projection

    with store.transaction() as tx:
        items = projection(tx, user, "unavailable")["products"]
        eligible_products = [
            p
            for p in items
            if p.get("active", True)
            and (not in_stock or p["available_stock"] > 0)
            and (
                not category
                or p.get("category", "General").casefold() == category.casefold()
            )
            and (not seller_id or p["seller_id"] == seller_id)
            and (not currency or p["currency"] == currency)
        ]
    from app.platform.search import ranked

    filtered, engine, warning = ranked(q, eligible_products)
    return {
        "items": filtered[offset : offset + limit],
        "total": len(filtered),
        "offset": offset,
        "limit": limit,
        "engine": engine,
        "warning": warning,
        "as_of": now(),
    }


@router.get("/geo/eligible-sellers")
def eligible(user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        zones = [
            z
            for z in tx.all("zones")
            if z.get("active", True) and service.inside_zone(user, z, tx)
        ]
        sellers = {z["seller_id"] for z in zones}
        return {
            "sellers": [
                {"id": u["id"], "name": u["name"], "verified": u.get("verified", False)}
                for u in tx.all("users")
                if u["id"] in sellers and u.get("verified", False)
            ],
            "zones": zones,
        }


@router.get("/procurement/requests/{request_id}")
def buying_request(
    request_id: str, user=Depends(current_user), store=Depends(store_for)
):
    with store.transaction() as tx:
        record = service.must(tx, "requests", request_id)
        commercial.access(user, record)
        return record


@router.get("/pools")
def pools(request: Request, user=Depends(current_user), store=Depends(store_for)):
    from app.platform.router import projection

    with store.transaction() as tx:
        return projection(tx, user, request.app.state.payments.mode)["pools"]


@router.get("/pools/{pool_id}")
def pool(
    pool_id: str, request: Request, user=Depends(current_user), store=Depends(store_for)
):
    record = next((p for p in pools(request, user, store) if p["id"] == pool_id), None)
    if not record:
        raise HTTPException(404, "Delivery pool not found")
    return record


@router.get("/pools/{pool_id}/allocations")
def allocations(
    pool_id: str, request: Request, user=Depends(current_user), store=Depends(store_for)
):
    return pool(pool_id, request, user, store)["allocations"]


@router.post("/pools/{pool_id}/lock")
def lock(pool_id: str, user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        record = service.must(tx, "pools", pool_id)
        service.seller_access(user, record["seller_id"])
        if record["status"] == "LOCKED":
            return record
        if record["status"] not in {"ACCUMULATING", "FAILED"}:
            raise HTTPException(409, "This pool cannot be locked")
        record.update(status="LOCKED", locked_at=now())
        tx.put("pools", record)
        tx.audit(user["id"], "POOL_LOCKED", pool_id)
        return record


@router.post("/pools/{pool_id}/optimize")
def optimize(pool_id: str, user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        try:
            return service.clear_pool(tx, user, service.must(tx, "pools", pool_id))
        except ValueError as error:
            raise HTTPException(422, str(error))


@router.get("/orders")
def orders(request: Request, user=Depends(current_user), store=Depends(store_for)):
    from app.platform.router import projection

    with store.transaction() as tx:
        return projection(tx, user, request.app.state.payments.mode)["orders"]


@router.get("/orders/{order_id}")
def order(order_id: str, user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        record = service.must(tx, "orders", order_id)
        service.order_access(tx, user, record)
        return record


@router.get("/dispatch/{pool_id}/manifest")
def manifest(pool_id: str, user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        record = service.must(tx, "pools", pool_id)
        if record.get("driver_id") != user["id"]:
            service.seller_access(user, record["seller_id"])
        if record["status"] not in {"CLEARED", "DISPATCHED", "COMPLETED"}:
            raise HTTPException(409, "A cleared allocation is required")
        zone = record.get("zone_snapshot") or service.must(
            tx, "zones", record["zone_id"]
        )
        stops = []
        for index, rid in enumerate(record.get("route", []), 1):
            allocation = next(
                a for a in record["allocations"] if a["request_id"] == rid
            )
            buyer = service.must(tx, "users", allocation["buyer_id"])
            point = allocation.get("delivery_location", buyer["location"])
            stops.append(
                {
                    "sequence": index,
                    "order_id": allocation["order_id"],
                    "business": allocation.get("buyer_name", buyer["name"]),
                    "location": allocation.get("delivery_location", buyer["location"]),
                    "quantity": allocation["quantity"],
                    "product": allocation.get("product_snapshot"),
                    "delivery_window": record.get("delivery_window"),
                    "navigation_url": f"https://www.google.com/maps/dir/?api=1&destination={point[1]},{point[0]}",
                }
            )
        return {
            "pool_id": pool_id,
            "version": record["version"],
            "agreement_hash": record["agreement_hash"],
            "dispatch_date": record["dispatch_date"],
            "depot": zone["depot"],
            "driver_id": record.get("driver_id"),
            "vehicle": record.get("vehicle_snapshot"),
            "stops": stops,
            "distance_model": "geographic, no road ETA",
        }


@router.get("/driver/routes/today")
def routes(user=Depends(current_user), store=Depends(store_for)):
    require_role(user, "DRIVER")
    with store.transaction() as tx:
        return [
            p
            for p in tx.all("pools")
            if p.get("driver_id") == user["id"] and p["status"] == "DISPATCHED"
        ]
