"""Persistent two-party offers. Neither an offer nor its acceptance is payment consent."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException

from app.platform import service
from app.platform.store import now


def access(user, offer):
    if (
        user["id"] not in {offer["buyer_id"], offer["seller_id"]}
        and "ADMIN" not in user["roles"]
    ):
        raise HTTPException(403, "This negotiation belongs to another business")


def require_party(user, buying):
    if not (
        (user["id"] == buying["buyer_id"] and "RETAILER" in user["roles"])
        or (user["id"] == buying["seller_id"] and "SELLER" in user["roles"])
    ):
        raise HTTPException(
            403, "An active buyer or supplier role is required to negotiate"
        )


def open_request(tx, user, request_id):
    buying = service.must(tx, "requests", request_id)
    access(user, buying)
    require_party(user, buying)
    if buying["status"] != "ACTIVE" or service.must(tx, "pools", buying["pool_id"])[
        "status"
    ] not in {"ACCUMULATING", "FAILED"}:
        raise HTTPException(
            409, "Negotiation requires an active, unlocked buying request"
        )
    return buying


def validate_terms(tx, buying, data, seller_authority=False):
    item = service.must(tx, "products", data["product_id"])
    permitted = {buying["product_id"], *buying.get("substitute_product_ids", [])}
    if item["id"] not in permitted or not item.get("active", True):
        raise HTTPException(422, "This SKU is not explicitly approved by the buyer")
    if (
        item["seller_id"] != buying["seller_id"]
        or item["currency"] != buying["currency"]
    ):
        raise HTTPException(
            422, "Offer currency or distributor does not match the request"
        )
    expected = buying.get("approved_product_specifications", {}).get(item["id"])
    if expected and expected != service.product_specification(item):
        raise HTTPException(
            409, "Product specifications changed; request renewed buyer consent"
        )
    if (
        not buying["quantity_min"]
        <= data["quantity_min"]
        <= data["quantity_max"]
        <= buying["quantity_max"]
    ):
        raise HTTPException(
            422, "An offer cannot expand the buyer-approved quantity interval"
        )
    if data["unit_price_minor"] > buying["ceiling_minor"]:
        raise HTTPException(
            422, "Base price already exceeds the delivered-price ceiling"
        )
    floor = item.get("negotiation_floor_minor") or min(
        t["unit_price_minor"] for t in item["tiers"]
    )
    if seller_authority and data["unit_price_minor"] < floor:
        raise HTTPException(
            422,
            "Price is below the seller-approved negotiation floor; revise catalog policy first",
        )
    if service.available_stock(tx).get(item["id"], 0) < data["quantity_min"]:
        raise HTTPException(409, "Insufficient available stock for the offered minimum")
    return item


def propose(tx, user, data, previous=None):
    buying = open_request(
        tx, user, data["request_id"] if previous is None else previous["request_id"]
    )
    if user["id"] not in {buying["buyer_id"], buying["seller_id"]}:
        raise HTTPException(
            403, "Only the buyer or distributor can propose commercial terms"
        )
    if previous:
        if (
            previous["status"] not in {"SUBMITTED", "COUNTERED"}
            or previous["version"] != data["version"]
        ):
            raise HTTPException(409, "This offer version is no longer open")
        if datetime.fromisoformat(previous["expires_at"]) <= datetime.now(UTC):
            raise HTTPException(409, "Offer expired; start a new proposal")
    item = validate_terms(tx, buying, data, user["id"] == buying["seller_id"])
    record = {
        "id": previous["id"] if previous else str(uuid4()),
        "request_id": buying["id"],
        "buyer_id": buying["buyer_id"],
        "seller_id": buying["seller_id"],
        "version": previous["version"] + 1 if previous else 1,
        "status": "COUNTERED" if previous else "SUBMITTED",
        "actor": user["id"],
        "currency": item["currency"],
        "unit": item["unit"],
        "terms": {
            k: data[k]
            for k in (
                "product_id",
                "quantity_min",
                "quantity_max",
                "unit_price_minor",
                "note",
            )
        },
        "expires_at": (
            datetime.now(UTC) + timedelta(hours=data["expires_in_hours"])
        ).isoformat(),
        "created_at": previous["created_at"] if previous else now(),
        "updated_at": now(),
        "validation": {
            "buyer_limits_preserved": True,
            "stock_checked": True,
            "freight": "Estimated separately; final clearing is mandatory",
        },
    }
    tx.put("offers", record)
    tx.put(
        "offer_revisions",
        {
            **record,
            "id": f"{record['id']}:{record['version']}",
            "offer_id": record["id"],
        },
    )
    tx.audit(
        user["id"],
        "OFFER_" + record["status"],
        record["id"],
        {"request_id": buying["id"], "version": record["version"]},
    )
    return record


def accept(tx, user, offer, version):
    access(user, offer)
    require_party(user, offer)
    if offer["status"] == "ACCEPTED" and offer["version"] == version:
        return offer
    buying = open_request(tx, user, offer["request_id"])
    if offer["version"] != version or offer["status"] not in {"SUBMITTED", "COUNTERED"}:
        raise HTTPException(409, "The offer version changed; review the latest terms")
    if user["id"] == offer["actor"] or user["id"] not in {
        offer["buyer_id"],
        offer["seller_id"],
    }:
        raise HTTPException(403, "The other party must accept these terms")
    if datetime.fromisoformat(offer["expires_at"]) <= datetime.now(UTC):
        raise HTTPException(409, "Offer expired")
    validate_terms(tx, buying, offer["terms"], True)
    old = tx.get("offers", buying.get("accepted_offer_id", ""))
    if old and old["id"] != offer["id"]:
        old["status"] = "SUPERSEDED"
        tx.put("offers", old)
    offer.update(status="ACCEPTED", accepted_by=user["id"], accepted_at=now())
    buying.update(accepted_offer_id=offer["id"], negotiated_terms=offer["terms"])
    tx.put("requests", buying)
    tx.put("offers", offer)
    tx.audit(
        user["id"],
        "OFFER_ACCEPTED",
        offer["id"],
        {"request_id": buying["id"], "version": version},
    )
    return offer


def reject(tx, user, offer, version):
    access(user, offer)
    open_request(tx, user, offer["request_id"])
    if user["id"] == offer["actor"]:
        raise HTTPException(403, "Only the other party can reject these terms")
    if offer["version"] != version:
        raise HTTPException(409, "The offer version changed; review the latest terms")
    if offer["status"] == "REJECTED":
        return offer
    if offer["status"] not in {"SUBMITTED", "COUNTERED"}:
        raise HTTPException(409, "Only an open proposal can be rejected")
    if datetime.fromisoformat(offer["expires_at"]) <= datetime.now(UTC):
        raise HTTPException(409, "Offer expired")
    offer.update(status="REJECTED", rejected_by=user["id"], rejected_at=now())
    tx.put("offers", offer)
    tx.audit(user["id"], "OFFER_REJECTED", offer["id"], {"version": version})
    return offer
