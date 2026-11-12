"""Self-service retailer accounts for the public sandbox demonstration."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field, model_validator

from app.platform.auth import (
    check_origin,
    issue_session,
    password_hash,
    public_user,
    set_session_cookie,
    store_for,
)
from app.platform.models import Input

router = APIRouter(prefix="/api/v1/auth", tags=["accounts"])


class Registration(Input):
    name: str = Field(min_length=2, max_length=200)
    email: str = Field(
        min_length=5, max_length=200, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    )
    password: str = Field(min_length=12, max_length=128)

    @model_validator(mode="after")
    def normalize(self):
        self.name = self.name.strip()
        self.email = self.email.strip().lower()
        if len(self.name) < 2 or self.email.endswith("@paypool.demo"):
            raise ValueError("Use your business name and a non-reserved email address")
        return self


@router.post("/register", status_code=201)
def register(
    data: Registration, request: Request, response: Response, store=Depends(store_for)
):
    check_origin(request)
    if not request.app.state.demo:
        raise HTTPException(403, "Self-registration is available in the sandbox demo")
    with store.transaction() as tx:
        if any(u["email"].lower() == data.email for u in tx.all("users")):
            raise HTTPException(
                409, "An account with this email already exists. Sign in instead."
            )
        user = tx.put(
            "users",
            {
                "id": str(uuid4()),
                "email": data.email,
                "name": data.name,
                "roles": ["RETAILER"],
                "location": [77.59, 12.96],
                "active": True,
                "verified": False,
                "demo_account": True,
                "password_hash": password_hash(data.password),
                "contact_email": data.email,
            },
        )
        token, csrf = issue_session(tx, user)
        tx.audit(user["id"], "ACCOUNT_REGISTERED", user["id"])
    set_session_cookie(response, token)
    return {
        "user": public_user(user),
        "csrf": csrf,
        "demo_mode": True,
        "payment_provider": request.app.state.payments.mode,
    }
