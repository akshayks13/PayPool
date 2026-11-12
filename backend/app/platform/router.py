import csv
import hashlib
import os
import secrets
import time
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from urllib.parse import urlencode
from uuid import uuid4
from zipfile import ZipFile

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.platform import payment_execution, service
from app.platform.auth import (
    authenticate,
    check_origin,
    current_user,
    issue_session,
    public_user,
    require_role,
    session_payload,
    store_for,
)
from app.platform.auth import (
    set_session_cookie as cookie,
)
from app.platform.models import (
    Delivery,
    Discovery,
    Dispatch,
    Login,
    Product,
    Profile,
    Refund,
    RoleGrant,
    Version,
    Zone,
)
from app.platform.models import Request as BuyingRequest
from app.platform.payments import PaymentError
from app.platform.seed import ACCOUNTS, DEMO_PASSWORD
from app.platform.store import now

router = APIRouter(prefix="/api/v1")


@router.get("/config")
def config(request: Request):
    return {
        "demo_mode": request.app.state.demo,
        "registration_enabled": request.app.state.demo,
        "payment_provider": request.app.state.payments.mode,
        "paypal_login_enabled": bool(os.getenv("PAYPAL_LOGIN_ENABLED") == "true"),
        "accounts": [
            {"id": a[0], "email": a[1], "name": a[2], "roles": a[3]} for a in ACCOUNTS
        ]
        if request.app.state.demo
        else [],
        "demo_password": DEMO_PASSWORD if request.app.state.demo else None,
    }


@router.post("/auth/login")
def login(data: Login, request: Request, response: Response, store=Depends(store_for)):
    check_origin(request)
    token, csrf, user = authenticate(store, data, allow_demo=request.app.state.demo)
    cookie(response, token)
    return {
        "user": user,
        "csrf": csrf,
        "demo_mode": request.app.state.demo,
        "payment_provider": request.app.state.payments.mode,
    }


@router.get("/me")
def me(request: Request, user=Depends(current_user)):
    return session_payload(request, user)


@router.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    user=Depends(current_user),
    store=Depends(store_for),
):
    with store.transaction() as tx:
        tx.delete(
            "sessions",
            hashlib.sha256(request.cookies["paypool_session"].encode()).hexdigest(),
        )
    response.delete_cookie("paypool_session", path="/")
    return {"signed_out": True}


@router.get("/auth/paypal/start")
def paypal_login(request: Request, store=Depends(store_for)):
    if (
        os.getenv("PAYPAL_LOGIN_ENABLED") != "true"
        or not request.app.state.payments.client_id
    ):
        raise HTTPException(
            503,
            "PayPal Login requires enabled Identity access and configured credentials",
        )
    state, browser = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    redirect = os.getenv(
        "PAYPAL_LOGIN_REDIRECT_URI", "http://localhost:3000/api/v1/auth/paypal/callback"
    )
    with store.transaction() as tx:
        tx.put(
            "oauth_states",
            {
                "id": state,
                "browser_hash": hashlib.sha256(browser.encode()).hexdigest(),
                "expires": time.time() + 600,
                "redirect": redirect,
            },
        )
    params = urlencode(
        {
            "flowEntry": "static",
            "client_id": request.app.state.payments.client_id,
            "scope": "openid profile email",
            "response_type": "code",
            "redirect_uri": redirect,
            "state": state,
        }
    )
    response = RedirectResponse("https://www.sandbox.paypal.com/connect?" + params)
    response.set_cookie(
        "paypool_oauth",
        browser,
        httponly=True,
        samesite="lax",
        max_age=600,
        secure=os.getenv("PAYPOOL_COOKIE_SECURE", "false").lower() == "true",
        path="/",
    )
    return response


@router.get("/auth/paypal/callback")
def paypal_callback(
    request: Request, state: str = "", code: str = "", store=Depends(store_for)
):
    if os.getenv("PAYPAL_LOGIN_ENABLED") != "true":
        raise HTTPException(503, "PayPal Login is disabled")
    with store.transaction() as tx:
        pending = tx.get("oauth_states", state)
        valid = (
            pending
            and pending["expires"] >= time.time()
            and secrets.compare_digest(
                pending["browser_hash"],
                hashlib.sha256(
                    request.cookies.get("paypool_oauth", "").encode()
                ).hexdigest(),
            )
        )
        if not valid or not code:
            raise HTTPException(400, "Invalid or expired login state")
        tx.delete("oauth_states", state)
    provider = request.app.state.payments
    try:
        token = httpx.post(
            provider.base + "/v1/oauth2/token",
            auth=(provider.client_id, provider.secret),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": pending["redirect"],
            },
            timeout=20,
        )
        token.raise_for_status()
        info = httpx.get(
            provider.base + "/v1/identity/openidconnect/userinfo",
            params={"schema": "openid"},
            headers={"Authorization": "Bearer " + token.json()["access_token"]},
            timeout=20,
        )
        info.raise_for_status()
        profile = info.json()
        subject = profile.get("user_id") or profile.get("sub")
        if not subject:
            raise ValueError("Missing provider identity")
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(502, "PayPal identity exchange failed")
    with store.transaction() as tx:
        # Match the stable provider subject, never an unverified email claim.
        user = next(
            (u for u in tx.all("users") if u.get("provider_subject") == subject), None
        )
        if not user:
            user = tx.put(
                "users",
                {
                    "id": str(uuid4()),
                    "name": profile.get("name", "PayPal retailer"),
                    "email": profile.get("email", ""),
                    "provider_subject": subject,
                    "roles": ["RETAILER"],
                    "location": [0, 0],
                    "active": True,
                    "verified": False,
                },
            )
        if not user.get("active", True):
            raise HTTPException(403, "Account is disabled")
        session, _ = issue_session(tx, user)
        tx.audit(user["id"], "PAYPAL_SIGNED_IN", user["id"])
    response = RedirectResponse(
        provider.frontend + "/" + user["roles"][0].lower(), status_code=303
    )
    cookie(response, session)
    response.delete_cookie("paypool_oauth", path="/")
    return response


def projection(tx, user, provider):
    roles, uid = user["roles"], user["id"]
    admin = "ADMIN" in roles
    products = tx.all("products")
    zones = tx.all("zones")
    assigned_zone_ids = {
        p["zone_id"] for p in tx.all("pools") if p.get("driver_id") == uid
    }
    visible_zones = [
        z
        for z in zones
        if admin
        or z["seller_id"] == uid
        or (
            "RETAILER" in roles
            and z.get("active", True)
            and service.inside_zone(user, z, tx)
        )
        or ("DRIVER" in roles and z["id"] in assigned_zone_ids)
    ]
    pools = []
    orders = tx.all("orders")
    for p in tx.all("pools"):
        own = admin or p["seller_id"] == uid or p.get("driver_id") == uid
        is_member = any(
            (tx.get("requests", r) or {}).get("buyer_id") == uid
            for r in p["request_ids"]
        )
        eligible = "RETAILER" in roles and p["zone_id"] in {
            z["id"] for z in visible_zones
        }
        if not (own or is_member or eligible):
            continue
        p["member_count"] = len(
            [
                r
                for r in p["request_ids"]
                if (tx.get("requests", r) or {}).get("status") == "ACTIVE"
            ]
        )
        p["included_count"] = len(p.get("allocations", []))
        p["authorized_count"] = sum(
            o["pool_id"] == p["id"] and o["payment_status"] == "AUTHORIZED"
            for o in orders
        )
        if not own:
            p["allocations"] = [
                a for a in p.get("allocations", []) if a["buyer_id"] == uid
            ]
            p.pop("request_ids", None)
            p.pop("route", None)
            p.pop("excluded", None)
        pools.append(p)
    allowed_orders = [
        o
        for o in orders
        if admin
        or uid in {o["buyer_id"], o["seller_id"]}
        or any(p["id"] == o["pool_id"] and p.get("driver_id") == uid for p in pools)
    ]
    allowed_requests = [
        r for r in tx.all("requests") if admin or uid in {r["buyer_id"], r["seller_id"]}
    ]
    visible_people = [
        (
            public_user(u)
            if admin or u["id"] == uid
            else {
                k: v
                for k, v in public_user(u).items()
                if k
                in {
                    "id",
                    "name",
                    "roles",
                    "verified",
                    "active",
                    "location",
                    "contact_email",
                    "contact_phone",
                    "business_address",
                    "city",
                    "country",
                    "postal_code",
                    "delivery_instructions",
                    "preferred_delivery_window",
                }
            }
        )
        for u in tx.all("users")
        if admin
        or u["id"] == uid
        or ("SELLER" in roles and "DRIVER" in u["roles"])
        or (
            "RETAILER" in roles
            and "SELLER" in u["roles"]
            and any(z["seller_id"] == u["id"] for z in visible_zones)
        )
        or (
            "SELLER" in roles
            and any(
                r["seller_id"] == uid and r["buyer_id"] == u["id"]
                for r in allowed_requests
            )
        )
        or any(
            o["buyer_id"] == u["id"] and (uid == o["seller_id"] or "DRIVER" in roles)
            for o in allowed_orders
        )
    ]
    stock = service.available_stock(tx)
    for p in products:
        p["available_stock"] = stock.get(p["id"], 0)
    products = [
        p
        for p in products
        if admin
        or p["seller_id"] == uid
        or (
            "RETAILER" in roles
            and p.get("active", True)
            and any(z["seller_id"] == p["seller_id"] for z in visible_zones)
        )
        or any(o["product_id"] == p["id"] for o in allowed_orders)
    ]
    return {
        "user": public_user(user),
        "payment_provider": provider,
        "products": products,
        "zones": visible_zones,
        "requests": allowed_requests,
        "pools": pools,
        "orders": allowed_orders,
        "people": visible_people,
        "audit": sorted(
            [
                a
                for a in tx.all("audit")
                if admin
                or a["actor"] == uid
                or a["subject"] in {o["id"] for o in allowed_orders}
            ],
            key=lambda a: a["at"],
            reverse=True,
        )[:100],
        "receipts": [service.smart_receipt(o) for o in allowed_orders],
        "notifications": sorted(
            [n for n in tx.all("notifications") if n["user_id"] == uid],
            key=lambda n: n["created_at"],
            reverse=True,
        )[:100],
    }


@router.get("/workspace")
def workspace(request: Request, user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        return projection(tx, user, request.app.state.payments.mode)


@router.patch("/me")
def profile(data: Profile, user=Depends(current_user), store=Depends(store_for)):
    lon, lat = data.location
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise HTTPException(422, "Invalid longitude / latitude")
    with store.transaction() as tx:
        user = service.must(tx, "users", user["id"])
        changes = data.model_dump(mode="json", exclude_unset=True)
        moving = any(
            changes.get(k, user.get(k, "")) != user.get(k, "")
            for k in ("location", "business_address", "city", "postal_code", "country")
        )
        if moving and any(
            r["buyer_id"] == user["id"]
            and r["status"] == "ACTIVE"
            and service.must(tx, "pools", r["pool_id"])["status"]
            not in {"CANCELLED", "COMPLETED", "FAILED"}
            for r in tx.all("requests")
        ):
            raise HTTPException(
                409,
                "Withdraw or complete your active orders before changing the delivery location",
            )
        user.update(changes)
        tx.put("users", user)
        tx.audit(user["id"], "PROFILE_UPDATED", user["id"], {"fields": sorted(changes)})
        return public_user(user)


@router.post("/seller/products")
def create_product(data: Product, user=Depends(current_user), store=Depends(store_for)):
    require_role(user, "SELLER")
    with store.transaction() as tx:
        if data.image_url.startswith("/api/v1/media/"):
            raise HTTPException(422, "Save the product before uploading its image")
        item = tx.put(
            "products",
            {
                **data.model_dump(mode="json"),
                "id": str(uuid4()),
                "seller_id": user["id"],
                "stock_updated_at": now(),
            },
        )
        tx.audit(user["id"], "PRODUCT_CREATED", item["id"])
        return item


@router.put("/seller/products/{product_id}")
def update_product(
    product_id: str, data: Product, user=Depends(current_user), store=Depends(store_for)
):
    with store.transaction() as tx:
        item = service.must(tx, "products", product_id)
        service.seller_access(user, item["seller_id"])
        from app.platform.media import validate_image_reference

        validate_image_reference(tx, data.image_url, product_id)
        reserved = item["stock"] - service.available_stock(tx).get(product_id, 0)
        if reserved:
            raise HTTPException(
                409,
                "This product has reserved allocations; complete or cancel those runs before editing",
            )
        tx.audit(user["id"], "PRODUCT_UPDATED", item["id"])
        return tx.put(
            "products",
            {
                **data.model_dump(mode="json"),
                "id": item["id"],
                "seller_id": item["seller_id"],
                "stock_updated_at": now(),
            },
        )


@router.post("/seller/zones")
def create_zone(data: Zone, user=Depends(current_user), store=Depends(store_for)):
    require_role(user, "SELLER")
    with store.transaction() as tx:
        zone = tx.put(
            "zones",
            {
                **data.model_dump(mode="json"),
                "id": str(uuid4()),
                "seller_id": user["id"],
                "created_at": now(),
            },
        )
        tx.audit(user["id"], "ZONE_CREATED", zone["id"])
        return zone


@router.post("/procurement/requests")
def submit(data: BuyingRequest, user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        return service.submit_request(tx, user, data.model_dump(mode="json"))


@router.post("/procurement/discover")
def discover(data: Discovery, user=Depends(current_user), store=Depends(store_for)):
    """Buyer/seller recommendations from persisted catalog and active demand.

    The buyer agent interprets a request, the seller agent evaluates its own
    configured tiers. Gemini can narrate those facts, but cannot invent terms.
    No request, quote approval, inventory reservation or payment is created.
    """
    require_role(user, "RETAILER")
    from app.platform import conversations

    if data.conversation_version is not None:
        with store.transaction() as tx:
            conversations.check(tx, user, data.conversation_version)
    from app.modules.negotiation.llm import (
        GeminiNegotiationNarrator,
        LLMUnavailableError,
        NegotiationNarrationFacts,
    )
    from app.modules.negotiation.procurement_router import get_procurement_parser
    from app.modules.negotiation.procurement_schemas import ProcurementParseRequest

    try:
        parser = get_procurement_parser()
        intent = parser.parse(
            ProcurementParseRequest(message=data.message, currency=data.currency)
        )
    except LLMUnavailableError as error:
        raise HTTPException(503, str(error))
    from app.modules.negotiation.llm import GeminiProcurementExtractor

    engine = (
        "gemini" if isinstance(parser, GeminiProcurementExtractor) else "deterministic"
    )
    if intent.clarification_questions:
        return {
            "intent": intent.model_dump(mode="json"),
            "candidates": [],
            "messages": [],
            "engine": engine,
            "conversation": conversations.save(store, user, data, intent, engine),
        }
    import re

    words = set(re.findall(r"[a-z]+", (intent.product_description or "").lower()))
    from app.platform.clearing import tier_price

    candidates, messages = [], []
    quantity = int(intent.quantity)
    if quantity < 1 or intent.quantity != quantity:
        raise HTTPException(
            422,
            "Use whole catalog units for this MVP; fractional units must be converted before ordering",
        )
    with store.transaction() as tx:
        stock = service.available_stock(tx)
        catalog = tx.all("products")
        requested_varieties = {
            p.get("attributes", {}).get("variety")
            for p in catalog
            if p.get("attributes", {}).get("variety")
            and p["attributes"]["variety"].casefold() in data.message.casefold()
        }
        for item in catalog:
            supplier = tx.get("users", item["seller_id"]) or {}
            if (
                not item.get("active", True)
                or not supplier.get("active", True)
                or not supplier.get("verified", False)
                or "SELLER" not in supplier.get("roles", [])
            ):
                continue
            if (
                requested_varieties
                and item.get("attributes", {}).get("variety") not in requested_varieties
            ):
                continue
            if (
                item["currency"] != data.currency
                or item["unit"] != intent.quantity_unit
                or stock.get(item["id"], 0) < quantity
            ):
                continue
            overlap = words.intersection(re.findall(r"[a-z]+", item["title"].lower()))
            if not overlap:
                continue
            for zone in tx.all("zones"):
                if (
                    not zone.get("active", True)
                    or zone["seller_id"] != item["seller_id"]
                    or zone.get("currency", "USD") != item["currency"]
                    or not service.inside_zone(user, zone, tx)
                ):
                    continue
                others = [
                    r
                    for r in tx.all("requests")
                    if r["product_id"] == item["id"]
                    and r["zone_id"] == zone["id"]
                    and r["dispatch_date"] == intent.delivery_date.isoformat()
                    and r["status"] == "ACTIVE"
                    and service.must(tx, "pools", r["pool_id"])["status"]
                    == "ACCUMULATING"
                ]
                total_q = quantity + sum(r["quantity_min"] for r in others)
                price = tier_price(item, total_q)
                # Advisory estimate only. Actual mixed-SKU normalized footprint
                # allocation is independently computed at pool clearing.
                route_fee = zone["base_freight_minor"] + zone["stop_fee_minor"] * (
                    len(others) + 1
                )
                freight = (route_fee * quantity + total_q - 1) // total_q
                estimated_total = price * quantity + freight
                standalone = (
                    tier_price(item, quantity) * quantity
                    + zone["base_freight_minor"]
                    + zone["stop_fee_minor"]
                )
                candidates.append(
                    {
                        "product_id": item["id"],
                        "seller_id": item["seller_id"],
                        "available_stock": stock[item["id"]],
                        "estimated_route_freight_minor": route_fee,
                        "zone_id": zone["id"],
                        "title": item["title"],
                        "quantity": quantity,
                        "currency": item["currency"],
                        "unit": item["unit"],
                        "unit_price_minor": price,
                        "estimated_total_minor": estimated_total,
                        "standalone_total_minor": standalone,
                        "within_ceiling": estimated_total
                        <= intent.price_ceiling_per_unit_minor * quantity,
                        "pool_quantity": total_q,
                        "requires_final_clearing": True,
                        "attribute_review_required": item.get("attributes", {}),
                        "other_requests": len(others),
                        "next_tier": next(
                            (
                                t
                                for t in item["tiers"]
                                if t["minimum_quantity"] > total_q
                            ),
                            None,
                        ),
                    }
                )
    from app.platform.agents import coordinate

    candidates, agent_trace = coordinate(
        intent, candidates, {p["id"]: p for p in catalog}
    )
    candidates.sort(key=lambda c: c["estimated_total_minor"])
    for c in candidates[:3]:
        messages.extend(
            [
                {
                    "speaker": "Buyer agent",
                    "message": f"Compared {c['title']} with your delivered-price ceiling. {'Estimated within ceiling' if c['within_ceiling'] else 'Needs more shared demand or a revised seller offer'}.",
                },
                {
                    "speaker": "Distributor agent",
                    "message": f"Current eligible demand is {c['pool_quantity']} {c['unit']}. Using only the configured earned price tier; stock and route capacity must pass final clearing.",
                },
            ]
        )
    narration_error = None
    if engine == "gemini" and candidates:
        c = candidates[0]
        try:
            narrator = GeminiNegotiationNarrator.from_environment()
            narrative = narrator.narrate(
                NegotiationNarrationFacts(
                    speaker="buyer",
                    product_title=c["title"],
                    quantity=str(quantity),
                    unit=c["unit"],
                    currency=c["currency"],
                    price_ceiling_per_unit_minor=intent.price_ceiling_per_unit_minor,
                    estimated_landed_unit_cost_minor=(
                        c["estimated_total_minor"] + quantity - 1
                    )
                    // quantity,
                    status="ESTIMATE_ONLY",
                    required_action="Review the exact product and create a buying request. Final clearing and approval are required.",
                )
            )
            messages.insert(
                0, {"speaker": "AI procurement copilot", "message": narrative.message}
            )
        except LLMUnavailableError as error:
            narration_error = str(error)
    return {
        "intent": intent.model_dump(mode="json"),
        "candidates": candidates,
        "messages": messages,
        "engine": engine,
        "narration_error": narration_error,
        "agent_trace": agent_trace,
        "conversation": conversations.save(store, user, data, intent, engine),
    }


@router.post("/procurement/requests/{request_id}/withdraw")
def withdraw(request_id: str, user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        record = service.must(tx, "requests", request_id)
        if record["buyer_id"] != user["id"]:
            raise HTTPException(403, "Only the buyer can withdraw this request")
        pool = service.must(tx, "pools", record["pool_id"])
        if pool["status"] not in {"ACCUMULATING", "FAILED"}:
            raise HTTPException(
                409, "This pool is locked; ask the distributor to cancel or replan it"
            )
        record["status"] = "WITHDRAWN"
        tx.audit(user["id"], "REQUEST_WITHDRAWN", record["id"])
        return tx.put("requests", record)


@router.post("/pools/{pool_id}/clear")
def clear(pool_id: str, user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        try:
            return service.clear_pool(tx, user, service.must(tx, "pools", pool_id))
        except ValueError as error:
            raise HTTPException(422, str(error))


@router.post("/pools/{pool_id}/approve")
def approve(
    pool_id: str, data: Version, user=Depends(current_user), store=Depends(store_for)
):
    with store.transaction() as tx:
        return service.approve(
            tx, user, service.must(tx, "pools", pool_id), data.version
        )


@router.post("/pools/{pool_id}/cancel")
def cancel(
    pool_id: str, request: Request, user=Depends(current_user), store=Depends(store_for)
):
    return payment_execution.cancel_pool(
        store, user, pool_id, request.app.state.payments
    )


@router.post("/pools/{pool_id}/replan")
def replan(
    pool_id: str,
    request: Request,
    exclude_request_id: str = "",
    user=Depends(current_user),
    store=Depends(store_for),
):
    with store.transaction() as tx:
        pool = service.must(tx, "pools", pool_id)
        service.seller_access(user, pool["seller_id"])
        if pool.get("replacement_pool_id"):
            if pool.get("excluded_request_id", "") != exclude_request_id:
                raise HTTPException(
                    409, "This pool was already replanned with different terms"
                )
            return service.must(tx, "pools", pool["replacement_pool_id"])
        if exclude_request_id and exclude_request_id not in pool["request_ids"]:
            raise HTTPException(422, "Excluded request does not belong to this pool")
    pool = payment_execution.cancel_pool(
        store, user, pool_id, request.app.state.payments
    )
    if pool["status"] != "CANCELLED":
        return pool
    with store.transaction() as tx:
        pool = service.must(tx, "pools", pool_id)
        if pool.get("replacement_pool_id"):
            if pool.get("excluded_request_id", "") != exclude_request_id:
                raise HTTPException(409, "This pool was replanned with different terms")
            return service.must(tx, "pools", pool["replacement_pool_id"])
        new = {
            k: pool[k] for k in ("seller_id", "zone_id", "dispatch_date", "currency")
        }
        new.update(
            id=str(uuid4()),
            status="ACCUMULATING",
            version=0,
            request_ids=[],
            allocations=[],
            created_at=now(),
            previous_pool_id=pool_id,
        )
        for key in pool["request_ids"]:
            r = service.must(tx, "requests", key)
            if key == exclude_request_id:
                r["status"] = "WITHDRAWN"
            elif r["status"] == "ACTIVE":
                r["pool_id"] = new["id"]
                new["request_ids"].append(key)
            tx.put("requests", r)
        tx.put("pools", new)
        pool["replacement_pool_id"] = new["id"]
        pool["excluded_request_id"] = exclude_request_id
        tx.put("pools", pool)
        if new["request_ids"]:
            savepoint = tx.connection.begin_nested()
            try:
                new = service.clear_pool(tx, user, new)
                savepoint.commit()
            except (HTTPException, ValueError) as error:
                savepoint.rollback()
                new.update(
                    status="FAILED",
                    allocations=[],
                    reason=str(getattr(error, "detail", error)),
                )
                tx.put("pools", new)
        tx.audit(user["id"], "POOL_REPLANNED", new["id"], {"previous_pool_id": pool_id})
        return new


@router.post("/pools/{pool_id}/dispatch")
def dispatch(
    pool_id: str,
    data: Dispatch,
    request: Request,
    user=Depends(current_user),
    store=Depends(store_for),
):
    provider = request.app.state.payments
    with store.transaction() as tx:
        pool = service.must(tx, "pools", pool_id)
        service.seller_access(user, pool["seller_id"])
        if pool["status"] != "CLEARED":
            raise HTTPException(409, "Only a cleared pool can be dispatched")
        order_ids = [a["order_id"] for a in pool.get("allocations", [])]
        if any(
            (tx.get("orders", key) or {}).get("payment_status") != "AUTHORIZED"
            or (tx.get("orders", key) or {}).get("payment_operation_id")
            for key in order_ids
        ):
            raise HTTPException(
                409, "Every buyer must finish authorization before dispatch"
            )
    if provider.mode != "demo":
        for key in order_ids:
            try:
                payment_execution.reconcile(store, user, key, provider)
            except PaymentError as error:
                raise HTTPException(502, str(error))
    with store.transaction() as tx:
        pool = service.must(tx, "pools", pool_id)
        if (
            provider.mode != "demo"
            and not data.vehicle_id
            and all(
                service.must(tx, "orders", key)["payment_status"] == "AUTHORIZED"
                for key in order_ids
            )
        ):
            raise HTTPException(422, "Assign a fleet vehicle before live dispatch")
        return service.dispatch(tx, user, pool, data.driver_id, data.vehicle_id)


@router.post("/orders/{order_id}/checkout")
def checkout(
    order_id: str,
    request: Request,
    user=Depends(current_user),
    store=Depends(store_for),
):
    with store.transaction() as tx:
        order = service.must(tx, "orders", order_id)
        service.order_access(tx, user, order)
        if request.app.state.payments.mode == "paypal_sandbox" and order[
            "seller_id"
        ] != os.getenv("PAYPAL_SELLER_ID", "seller-demo"):
            raise HTTPException(
                409, "This distributor is not connected to the sandbox merchant account"
            )
    return payment_execution.execute(
        store, user, order_id, request.app.state.payments, "checkout"
    )


@router.post("/orders/{order_id}/authorize")
def authorize(
    order_id: str,
    request: Request,
    user=Depends(current_user),
    store=Depends(store_for),
):
    return payment_execution.execute(
        store, user, order_id, request.app.state.payments, "authorize"
    )


@router.post("/orders/{order_id}/reconcile")
def reconcile(
    order_id: str,
    request: Request,
    user=Depends(current_user),
    store=Depends(store_for),
):
    try:
        return payment_execution.reconcile(
            store, user, order_id, request.app.state.payments
        )
    except PaymentError as error:
        raise HTTPException(502, str(error))


@router.post("/orders/{order_id}/pod")
def pod(
    order_id: str,
    data: Delivery,
    request: Request,
    user=Depends(current_user),
    store=Depends(store_for),
):
    with store.transaction() as tx:
        order = service.delivery(
            tx,
            user,
            service.must(tx, "orders", order_id),
            data.model_dump(mode="json"),
            request.app.state.payments,
            defer_capture=True,
        )
    if order.get("capture_requested"):
        return payment_execution.execute(
            store, user, order_id, request.app.state.payments, "capture"
        )
    return order


@router.post("/orders/{order_id}/capture")
def capture(
    order_id: str,
    request: Request,
    user=Depends(current_user),
    store=Depends(store_for),
):
    return payment_execution.execute(
        store, user, order_id, request.app.state.payments, "capture"
    )


@router.get("/orders/{order_id}/receipt")
def receipt(order_id: str, user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        order = service.must(tx, "orders", order_id)
        service.order_access(tx, user, order)
        return service.smart_receipt(order)


@router.post("/orders/{order_id}/refund")
def refund(
    order_id: str,
    data: Refund,
    request: Request,
    user=Depends(current_user),
    store=Depends(store_for),
):
    return payment_execution.refund(
        store,
        user,
        order_id,
        data,
        request.headers.get("Idempotency-Key", ""),
        request.app.state.payments,
    )


def sha_key(value):
    return hashlib.sha256(value.encode()).hexdigest()


@router.post("/webhooks/paypal")
async def webhook(request: Request, store=Depends(store_for)):
    if len(await request.body()) > 1000000:
        raise HTTPException(413, "Webhook is too large")
    try:
        event = await request.json()
    except ValueError:
        raise HTTPException(400, "Malformed webhook JSON")
    if not isinstance(event, dict) or not isinstance(event.get("id"), str):
        raise HTTPException(400, "Malformed webhook")
    provider = request.app.state.payments
    try:
        await run_in_threadpool(provider.verify_webhook, request.headers, event)
    except PaymentError as error:
        raise HTTPException(400, str(error))
    matched_id = await run_in_threadpool(record_verified_event, store, event)
    if matched_id == "duplicate":
        return {"duplicate": True}
    if matched_id:
        with store.transaction() as tx:
            order = service.must(tx, "orders", matched_id)
            actor = service.must(tx, "users", order["seller_id"])
        try:
            await run_in_threadpool(
                payment_execution.reconcile, store, actor, matched_id, provider
            )
            with store.transaction() as tx:
                saved = service.must(tx, "payment_events", event["id"])
                saved["status"] = "PROCESSED"
                tx.put("payment_events", saved)
        except (PaymentError, HTTPException):
            # The verified event is durable. The worker retries reconciliation
            # after an in-flight operation completes or the provider recovers.
            pass
    return {"received": True}


def record_verified_event(store, event):
    with store.transaction() as tx:
        previous = tx.get("payment_events", event["id"])
        if previous and previous.get("status") in {"PROCESSED", "IGNORED"}:
            return "duplicate"
        resource = event.get("resource", {})
        related = resource.get("supplementary_data", {}).get("related_ids", {})
        identifiers = {
            str(v)
            for v in (
                resource.get("id"),
                related.get("order_id"),
                related.get("capture_id"),
                related.get("authorization_id"),
            )
            if v
        }
        matched = next(
            (
                o
                for o in tx.all("orders")
                if identifiers.intersection(
                    {
                        o.get("provider_order_id"),
                        o.get("authorization_id"),
                        o.get("capture_id"),
                    }
                )
            ),
            None,
        )
        if matched:
            if (
                event.get("event_type", "").startswith("PAYMENT.CAPTURE.")
                and event["event_type"] != "PAYMENT.CAPTURE.REFUNDED"
            ):
                capture_id = related.get("capture_id") or resource.get("id")
                if capture_id:
                    matched["capture_id"] = capture_id
                    tx.put("orders", matched)
            if event.get("event_type") == "PAYMENT.CAPTURE.REFUNDED":
                from app.platform.payments import amount

                pending = [
                    r
                    for r in tx.all("refunds")
                    if r["order_id"] == matched["id"]
                    and not r.get("provider_refund_id")
                    and r["status"] in {"PENDING", "REQUIRES_RECONCILIATION"}
                    and resource.get("amount")
                    == {
                        "currency_code": matched["currency"],
                        "value": amount(r["amount_minor"]),
                    }
                ]
                if len(pending) == 1 and resource.get("id"):
                    pending[0]["provider_refund_id"] = resource["id"]
                    tx.put("refunds", pending[0])
            if not previous:
                tx.audit(
                    matched["seller_id"],
                    "PROVIDER_EVENT_VERIFIED",
                    matched["id"],
                    {"event_id": event["id"]},
                )
        tx.put(
            "payment_events",
            {
                "id": event["id"],
                "type": event.get("event_type"),
                "received_at": now(),
                "order_id": matched["id"] if matched else None,
                "status": "PENDING" if matched else "IGNORED",
            },
        )
        return matched["id"] if matched else None


@router.post("/notifications/{notification_id}/read")
def read_notification(
    notification_id: str, user=Depends(current_user), store=Depends(store_for)
):
    with store.transaction() as tx:
        notification = service.must(tx, "notifications", notification_id)
        if notification["user_id"] != user["id"]:
            raise HTTPException(403, "This notification belongs to another account")
        notification["read"] = True
        return tx.put("notifications", notification)


@router.post("/admin/users/{user_id}/roles")
def grant(
    user_id: str, data: RoleGrant, user=Depends(current_user), store=Depends(store_for)
):
    require_role(user, "ADMIN")
    if user_id == user["id"]:
        raise HTTPException(403, "Another administrator must change your roles")
    with store.transaction() as tx:
        target = service.must(tx, "users", user_id)
        target["roles"] = sorted(set([*target["roles"], data.role]))
        tx.put("users", target)
        tx.audit(user["id"], "ROLE_GRANTED", user_id, {"role": data.role})
        return public_user(target)


@router.post("/admin/users/{user_id}/roles/revoke")
def revoke_role(
    user_id: str, data: RoleGrant, user=Depends(current_user), store=Depends(store_for)
):
    require_role(user, "ADMIN")
    if user_id == user["id"]:
        raise HTTPException(403, "Another administrator must change your roles")
    with store.transaction() as tx:
        target = service.must(tx, "users", user_id)
        if data.role not in target["roles"]:
            return public_user(target)
        target["roles"] = [role for role in target["roles"] if role != data.role]
        tx.put("users", target)
        tx.audit(user["id"], "ROLE_REVOKED", user_id, {"role": data.role})
        return public_user(target)


@router.post("/admin/users/{user_id}/verify")
def verify(user_id: str, user=Depends(current_user), store=Depends(store_for)):
    require_role(user, "ADMIN")
    with store.transaction() as tx:
        target = service.must(tx, "users", user_id)
        target["verified"] = True
        tx.put("users", target)
        tx.audit(user["id"], "BUSINESS_VERIFIED", user_id)
        return public_user(target)


@router.post("/seller/imports/preview")
async def preview(
    file: UploadFile = File(...), user=Depends(current_user), store=Depends(store_for)
):
    require_role(user, "SELLER")
    raw = await file.read(2000001)
    if len(raw) > 2000000:
        raise HTTPException(413, "Maximum file size is 2 MB")
    try:
        if (file.filename or "").lower().endswith(".xlsx"):
            with ZipFile(BytesIO(raw)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 10000000:
                    raise ValueError("Spreadsheet expands beyond the 10 MB limit")
            from openpyxl import load_workbook

            book = load_workbook(BytesIO(raw), read_only=True, data_only=True)
            rows = book.active.iter_rows(values_only=True)
            headers = [str(h or "").strip().lower() for h in next(rows)]
            source = [dict(zip(headers, row)) for _, row in zip(range(1001), rows)]
            book.close()
        elif (file.filename or "").lower().endswith(".csv"):
            source = list(csv.DictReader(StringIO(raw.decode("utf-8-sig"))))
        else:
            raise ValueError("Upload a CSV or XLSX file")
        if len(source) > 1000:
            raise ValueError("Maximum 1,000 products per import")
        valid, errors = [], []
        for index, row in enumerate(source, start=2):
            row = {
                str(k).strip().lower().replace(" ", "_"): v for k, v in row.items() if k
            }
            try:
                title = row.get("title") or row.get("product_name") or row.get("name")
                price = int(
                    (
                        Decimal(str(row.get("price") or row.get("unit_price"))) * 100
                    ).to_integral_exact()
                )
                item = Product(
                    title=title,
                    description=str(row.get("description") or ""),
                    category=str(row.get("category") or "General"),
                    pack=str(row.get("pack") or ""),
                    image_url=str(row.get("image_url") or ""),
                    product_url=str(row.get("product_url") or ""),
                    attributes={
                        key: str(row[key])
                        for key in ("brand", "variety", "size", "material")
                        if row.get(key)
                    },
                    unit=row.get("unit") or "kg",
                    currency=str(row.get("currency") or "USD").upper(),
                    stock=int(row.get("stock") or row.get("stock_quantity") or 0),
                    weight_grams=int(row.get("weight_grams") or 1000),
                    volume_cm3=int(row.get("volume_cm3") or 1500),
                    tiers=[{"minimum_quantity": 1, "unit_price_minor": price}],
                )
                valid.append(item.model_dump(mode="json"))
            except (ValueError, TypeError, InvalidOperation, ValidationError):
                errors.append(
                    {
                        "row": index,
                        "message": "Check product name, positive price, integer stock and supported currency",
                    }
                )
    except Exception as error:
        raise HTTPException(
            422,
            str(error)
            if isinstance(error, ValueError)
            else "Could not read this spreadsheet",
        )
    with store.transaction() as tx:
        return tx.put(
            "imports",
            {
                "id": str(uuid4()),
                "seller_id": user["id"],
                "filename": file.filename,
                "products": valid,
                "errors": errors,
                "status": "REVIEW",
                "created_at": now(),
            },
        )


@router.post("/seller/imports/{import_id}/commit")
def commit_import(import_id: str, user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        batch = service.must(tx, "imports", import_id)
        service.seller_access(user, batch["seller_id"])
        if batch["status"] == "IMPORTED":
            return batch
        if not batch["products"]:
            raise HTTPException(422, "No valid rows to import")
        ids = []
        for data in batch["products"]:
            ids.append(
                tx.put(
                    "products",
                    {
                        **data,
                        "id": str(uuid4()),
                        "seller_id": batch["seller_id"],
                        "stock_updated_at": now(),
                    },
                )["id"]
            )
        batch.update(status="IMPORTED", product_ids=ids)
        tx.put("imports", batch)
        tx.audit(user["id"], "CATALOG_IMPORTED", batch["id"], {"count": len(ids)})
        return batch
