"""Version-pinned ACP continuation adapter. Delegated payment completion is gated.

Uses the upstream 2026-04-17 schemas verbatim. A session can only reference a
buyer-approved authoritative allocation; it cannot negotiate or approve one.
"""

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from jsonschema import Draft202012Validator, FormatChecker

from app.platform import service
from app.platform.store import now

VERSION = "2026-04-17"
CONTRACT = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "acp"
    / VERSION
    / "schema.agentic_checkout.json"
)
if not CONTRACT.exists():
    CONTRACT = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / "acp"
        / VERSION
        / "schema.agentic_checkout.json"
    )
router = APIRouter(
    prefix="/acp", tags=["ACP · continuation, delegated payments disabled"]
)


class ProtocolError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def validate(name, payload):
    schema = json.loads(CONTRACT.read_text())
    document = {"$ref": f"#/$defs/{name}", "$defs": schema["$defs"]}
    errors = list(
        Draft202012Validator(document, format_checker=FormatChecker()).iter_errors(
            payload
        )
    )
    if errors:
        # Never echo payment credentials or entire upstream validation objects.
        raise ProtocolError(
            400, "invalid_schema", f"Payload does not match ACP {VERSION} {name}"
        )


def context(request: Request):
    if os.getenv("ACP_ENABLED", "false").lower() != "true":
        raise ProtocolError(
            503,
            "integration_disabled",
            "External checkout is disabled pending merchant eligibility",
        )
    if request.headers.get("API-Version") != VERSION:
        raise ProtocolError(
            400, "unsupported_api_version", f"Supported API-Version: {VERSION}"
        )
    authorization = request.headers.get("Authorization", "")
    token = (
        authorization.removeprefix("Bearer ")
        if authorization.startswith("Bearer ")
        else ""
    )
    identity = hashlib.sha256(token.encode()).hexdigest()
    with request.app.state.store.transaction() as tx:
        client = tx.get("agent_access", identity)
        if (
            not client
            or not client["active"]
            or datetime.fromisoformat(client["expires_at"]) <= datetime.now(UTC)
        ):
            raise ProtocolError(
                401,
                "invalid_agent_access",
                "Agent access is missing, revoked or expired",
            )
        user = service.must(tx, "users", client["buyer_id"])
        if not user.get("active", True) or "RETAILER" not in user["roles"]:
            raise ProtocolError(
                403, "buyer_unavailable", "The buyer account is unavailable"
            )
    return {"client": client, "user": user}


def approved_order(tx, user, order_id):
    order = tx.get("orders", order_id)
    if not order or order["buyer_id"] != user["id"]:
        raise ProtocolError(
            404, "quote_not_found", "Buyer-approved quote was not found"
        )
    pool = service.must(tx, "pools", order["pool_id"])
    if (
        pool["status"] != "CLEARED"
        or pool["agreement_hash"] != order["agreement_hash"]
        or order["status"] == "CANCELLED"
    ):
        raise ProtocolError(
            409,
            "quote_changed",
            "The agreed pool changed; renewed buyer approval is required",
        )
    return order


def check_items(payload, order):
    if "currency" in payload and payload["currency"].upper() != order["currency"]:
        raise ProtocolError(409, "currency_mismatch", "Use the quote's currency")
    if "line_items" in payload:
        items = payload["line_items"]
        if len(items) != 1 or items[0]["id"] != order["product_id"]:
            raise ProtocolError(
                409, "items_changed", "Items must match the approved pooled allocation"
            )
        if (
            "unit_amount" in items[0]
            and items[0]["unit_amount"] != order["unit_price_minor"]
        ):
            raise ProtocolError(
                409, "price_mismatch", "The merchant quote determines the price"
            )


def state(session, order):
    subtotal = order["quantity"] * order["unit_price_minor"]
    result = {
        "id": session["id"],
        "protocol": {"version": VERSION},
        "status": session["status"],
        "currency": order["currency"].lower(),
        "capabilities": {},
        "line_items": [
            {
                "id": order["id"],
                "item": {"id": order["product_id"]},
                "quantity": order["quantity"],
                "name": order.get("product_snapshot", {}).get(
                    "title", order["product_id"]
                ),
                "unit_amount": order["unit_price_minor"],
                "totals": [
                    {
                        "type": "subtotal",
                        "display_text": "Goods (tax included)",
                        "amount": subtotal,
                    },
                    {
                        "type": "total",
                        "display_text": "Goods total",
                        "amount": subtotal,
                    },
                ],
            }
        ],
        "totals": [
            {
                "type": "subtotal",
                "display_text": "Goods (tax included)",
                "amount": subtotal,
            },
            {
                "type": "fulfillment",
                "display_text": "Locked shared freight",
                "amount": order["freight_minor"],
            },
            {
                "type": "total",
                "display_text": "Agreed total",
                "amount": order["total_minor"],
            },
        ],
        "fulfillment_options": [],
        "messages": [
            {
                "type": "info",
                "content_type": "plain",
                "content": "Complete explicit PayPal approval in PayPool. Delegated agent payment processing is not enabled.",
                "resolution": "requires_buyer_review",
            }
        ],
        "links": [],
        "continue_url": os.getenv("PAYPOOL_FRONTEND_URL", "http://localhost:3000")
        + "/retailer/orders",
        "quote_id": order["id"],
        "created_at": session["created_at"],
        "expires_at": session["expires_at"],
        "updated_at": session["updated_at"],
    }
    validate("CheckoutSession", result)
    return result


async def body(request, name):
    if len(await request.body()) > 100000:
        raise ProtocolError(413, "body_too_large", "Request exceeds the size limit")
    try:
        payload = await request.json()
    except ValueError:
        raise ProtocolError(400, "invalid_json", "Expected a JSON request")
    validate(name, payload)
    return payload


def operation(tx, ctx, request, payload):
    key = request.headers.get("Idempotency-Key", "")
    if not 1 <= len(key) <= 255:
        raise ProtocolError(
            400, "idempotency_key_required", "Every POST requires Idempotency-Key"
        )
    identity = hashlib.sha256(
        f"{ctx['client']['id']}:{request.url.path}:{key}".encode()
    ).hexdigest()
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    previous = tx.get("acp_operations", identity)
    if previous and previous["digest"] != digest:
        raise ProtocolError(
            409, "idempotency_conflict", "This key was used with other request terms"
        )
    return identity, digest, previous


@router.post("/checkout_sessions", status_code=201)
async def create(request: Request, ctx=Depends(context)):
    payload = await body(request, "CheckoutSessionCreateRequest")
    with request.app.state.store.transaction() as tx:
        identity, digest, previous = operation(tx, ctx, request, payload)
        if previous:
            return JSONResponse(previous["response"], status_code=201)
        order = approved_order(tx, ctx["user"], payload.get("quote_id", ""))
        check_items(payload, order)
        session = tx.put(
            "acp_checkout_sessions",
            {
                "id": str(uuid4()),
                "buyer_id": ctx["user"]["id"],
                "client_id": ctx["client"]["id"],
                "order_id": order["id"],
                "agreement_hash": order["agreement_hash"],
                "status": "requires_escalation",
                "created_at": now(),
                "updated_at": now(),
                "expires_at": (datetime.now(UTC) + timedelta(minutes=15)).isoformat(),
            },
        )
        result = state(session, order)
        tx.put("acp_operations", {"id": identity, "digest": digest, "response": result})
        tx.audit(
            ctx["user"]["id"],
            "ACP_SESSION_CREATED",
            order["id"],
            {"session_id": session["id"]},
        )
        return JSONResponse(result, status_code=201)


def owned_session(tx, ctx, session_id):
    session = tx.get("acp_checkout_sessions", session_id)
    if not session or session["client_id"] != ctx["client"]["id"]:
        raise ProtocolError(404, "session_not_found", "Checkout session was not found")
    if datetime.fromisoformat(session["expires_at"]) <= datetime.now(UTC):
        session["status"] = "expired"
    return session


@router.get("/checkout_sessions/{session_id}")
def retrieve(session_id: str, request: Request, ctx=Depends(context)):
    with request.app.state.store.transaction() as tx:
        session = owned_session(tx, ctx, session_id)
        order = tx.get("orders", session["order_id"])
        if not order:
            raise ProtocolError(404, "quote_not_found", "Quote no longer exists")
        pool = service.must(tx, "pools", order["pool_id"])
        if (
            pool["status"] != "CLEARED"
            or pool["agreement_hash"] != session["agreement_hash"]
        ):
            session["status"] = "expired"
        tx.put("acp_checkout_sessions", session)
        return state(session, order)


@router.post("/checkout_sessions/{session_id}")
async def update(session_id: str, request: Request, ctx=Depends(context)):
    payload = await body(request, "CheckoutSessionUpdateRequest")
    return change(request, ctx, session_id, payload, "update")


@router.post("/checkout_sessions/{session_id}/complete")
async def complete(session_id: str, request: Request, ctx=Depends(context)):
    payload = await body(request, "CheckoutSessionCompleteRequest")
    # Tokens are neither persisted nor forwarded without eligible merchant
    # access. The protocol returns a buyer continuation state, never paid.
    return change(request, ctx, session_id, payload, "complete")


@router.post("/checkout_sessions/{session_id}/cancel")
async def cancel(session_id: str, request: Request, ctx=Depends(context)):
    payload = {}
    return change(request, ctx, session_id, payload, "cancel")


def change(request, ctx, session_id, payload, action):
    with request.app.state.store.transaction() as tx:
        identity, digest, previous = operation(tx, ctx, request, payload)
        if previous:
            return previous["response"]
        session = owned_session(tx, ctx, session_id)
        if session["status"] in {"canceled", "expired"} and action != "cancel":
            raise ProtocolError(
                409, "session_closed", "This checkout session is no longer open"
            )
        order = approved_order(tx, ctx["user"], session["order_id"])
        check_items(payload, order)
        if (
            payload.get("fulfillment_details")
            or payload.get("fulfillment_groups")
            or payload.get("selected_fulfillment_options")
        ):
            raise ProtocolError(
                409,
                "fulfillment_locked",
                "Delivery is fixed by the buyer-approved pool agreement",
            )
        if action == "cancel":
            session["status"] = "canceled"
        session["updated_at"] = now()
        tx.put("acp_checkout_sessions", session)
        result = state(session, order)
        tx.put("acp_operations", {"id": identity, "digest": digest, "response": result})
        tx.audit(
            ctx["user"]["id"],
            "ACP_SESSION_" + action.upper(),
            order["id"],
            {"session_id": session_id},
        )
        return result
