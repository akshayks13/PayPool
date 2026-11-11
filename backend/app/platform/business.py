"""Business profiles, supplier applications and operator account controls."""

from fastapi import APIRouter, Depends, HTTPException

from app.platform.auth import current_user, public_user, require_role, store_for
from app.platform.models import AccountState, SellerApplication, SellerReview
from app.platform.service import must
from app.platform.store import now

router = APIRouter(prefix="/api/v1", tags=["business accounts"])


@router.get("/me/seller-application")
def application(user=Depends(current_user), store=Depends(store_for)):
    with store.transaction() as tx:
        return tx.get("seller_applications", user["id"]) or {
            "status": "NOT_SUBMITTED",
            "version": 0,
        }


@router.post("/me/seller-application")
def apply(
    data: SellerApplication, user=Depends(current_user), store=Depends(store_for)
):
    with store.transaction() as tx:
        target = must(tx, "users", user["id"])
        if "SELLER" in target["roles"] and target.get("verified"):
            raise HTTPException(409, "Your supplier account is already approved")
        previous = tx.get("seller_applications", user["id"])
        if previous and previous["status"] == "PENDING":
            raise HTTPException(409, "Your application is already awaiting review")
        record = {
            "id": user["id"],
            "user_id": user["id"],
            **data.model_dump(),
            "version": (previous or {}).get("version", 0) + 1,
            "status": "PENDING",
            "submitted_at": now(),
            "review_note": "",
        }
        tx.put("seller_applications", record)
        tx.put(
            "seller_application_revisions",
            {**record, "id": f"{record['id']}:{record['version']}"},
        )
        tx.audit(user["id"], "SELLER_APPLICATION_SUBMITTED", user["id"])
        return record


@router.get("/admin/seller-applications")
def applications(user=Depends(current_user), store=Depends(store_for)):
    require_role(user, "ADMIN")
    with store.transaction() as tx:
        return sorted(
            tx.all("seller_applications"), key=lambda a: a["submitted_at"], reverse=True
        )


@router.post("/admin/seller-applications/{user_id}/review")
def review(
    user_id: str,
    data: SellerReview,
    user=Depends(current_user),
    store=Depends(store_for),
):
    require_role(user, "ADMIN")
    if user_id == user["id"]:
        raise HTTPException(403, "Another administrator must review your application")
    with store.transaction() as tx:
        record = must(tx, "seller_applications", user_id)
        if record["version"] != data.version or record["status"] != "PENDING":
            raise HTTPException(
                409, "This application changed or has already been reviewed"
            )
        target = must(tx, "users", user_id)
        if not target.get("active", True):
            raise HTTPException(
                409, "Reactivate the account before reviewing its application"
            )
        record.update(
            status=data.decision,
            review_note=data.note,
            reviewed_at=now(),
            reviewed_by=user["id"],
            version=record["version"] + 1,
        )
        if data.decision == "APPROVED":
            target["roles"] = sorted(set([*target["roles"], "SELLER"]))
            target["verified"] = True
            tx.put("users", target)
        tx.put("seller_applications", record)
        tx.put(
            "seller_application_revisions",
            {**record, "id": f"{record['id']}:{record['version']}"},
        )
        tx.audit(
            user["id"],
            "SELLER_APPLICATION_" + data.decision,
            user_id,
            {"note": data.note},
        )
        return record


@router.post("/admin/users/{user_id}/state")
def account_state(
    user_id: str,
    data: AccountState,
    user=Depends(current_user),
    store=Depends(store_for),
):
    require_role(user, "ADMIN")
    if user_id == user["id"]:
        raise HTTPException(403, "Another administrator must change your account state")
    with store.transaction() as tx:
        actor = must(tx, "users", user["id"])
        if not actor.get("active", True) or "ADMIN" not in actor["roles"]:
            raise HTTPException(403, "Your administrator access is no longer active")
        target = must(tx, "users", user_id)
        if target.get("active", True) == data.active:
            return public_user(target)
        if not data.active:
            if any(
                user_id in {o["buyer_id"], o["seller_id"]}
                and (
                    o["status"] not in {"DELIVERED", "CANCELLED"}
                    or o["payment_status"]
                    not in {"CAPTURED", "VOIDED", "REFUNDED", "NOT_STARTED"}
                )
                for o in tx.all("orders")
            ):
                raise HTTPException(
                    409,
                    "Resolve outstanding orders and payments before disabling this account",
                )
            if any(
                user_id in {r["buyer_id"], r["seller_id"]}
                and r["status"] == "ACTIVE"
                and must(tx, "pools", r["pool_id"])["status"]
                not in {"CANCELLED", "COMPLETED", "FAILED"}
                for r in tx.all("requests")
            ):
                raise HTTPException(
                    409, "Resolve active buying requests before disabling this account"
                )
            if any(
                p.get("driver_id") == user_id and p["status"] == "DISPATCHED"
                for p in tx.all("pools")
            ):
                raise HTTPException(
                    409, "Complete assigned deliveries before disabling this driver"
                )
            for session in tx.all("sessions"):
                if session["user_id"] == user_id:
                    tx.delete("sessions", session["id"])
        target.update(active=data.active)
        tx.put("users", target)
        tx.audit(
            user["id"],
            "ACCOUNT_REACTIVATED" if data.active else "ACCOUNT_DISABLED",
            user_id,
            {"reason": data.reason},
        )
        return public_user(target)
