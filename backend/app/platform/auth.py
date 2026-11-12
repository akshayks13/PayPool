import hashlib
import hmac
import os
import secrets
import time

from fastapi import Depends, HTTPException, Request

from app.platform.models import Login


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=16384, r=8, p=1
    ).hex()
    return salt + ":" + digest


def public_user(user):
    return {
        k: v for k, v in user.items() if k not in {"password_hash", "provider_subject"}
    }


def set_session_cookie(response, token):
    response.set_cookie(
        "paypool_session",
        token,
        httponly=True,
        samesite="lax",
        max_age=8 * 3600,
        secure=os.getenv("PAYPOOL_COOKIE_SECURE", "false").lower() == "true",
        path="/",
    )


def store_for(request: Request):
    return request.app.state.store


def check_origin(request: Request):
    origin = request.headers.get("origin")
    allowed = os.getenv("PAYPOOL_FRONTEND_URL", "http://localhost:3000")
    if origin and origin.rstrip("/") != allowed.rstrip("/"):
        raise HTTPException(403, "Request origin is not allowed")


def current_user(request: Request, store=Depends(store_for)):
    token = request.cookies.get("paypool_session", "")
    with store.transaction() as tx:
        session = (
            tx.get("sessions", hashlib.sha256(token.encode()).hexdigest())
            if token
            else None
        )
        if not session or session["expires"] < time.time():
            raise HTTPException(401, "Sign in to continue")
        user = tx.get("users", session["user_id"])
        if (
            not user
            or not user.get("active", True)
            or (
                not request.app.state.demo
                and (
                    user.get("demo_account")
                    or user.get("email", "").endswith("@paypool.demo")
                )
            )
        ):
            raise HTTPException(401, "Account is unavailable")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not hmac.compare_digest(
                request.headers.get("X-CSRF-Token", ""), session["csrf"]
            ):
                raise HTTPException(403, "Invalid CSRF token; refresh your session")
            check_origin(request)
    return user


def require_role(user, *roles):
    if not set(user["roles"]).intersection(roles):
        raise HTTPException(403, "This action is not permitted for your role")


def session_payload(request, user):
    raw = request.cookies.get("paypool_session", "")
    with request.app.state.store.transaction() as tx:
        session = tx.get("sessions", hashlib.sha256(raw.encode()).hexdigest())
    return {
        "user": public_user(user),
        "csrf": session["csrf"],
        "demo_mode": request.app.state.demo,
        "payment_provider": request.app.state.payments.mode,
    }


def issue_session(tx, user):
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    tx.put(
        "sessions",
        {
            "id": hashlib.sha256(token.encode()).hexdigest(),
            "user_id": user["id"],
            "csrf": csrf,
            "expires": time.time() + 8 * 3600,
        },
    )
    return token, csrf


def authenticate(store, login: Login, allow_demo=False):
    # Failed attempts are stored as well, so restarting a worker does not reset
    # the account's short lockout window.
    email = login.email.strip().lower()
    with store.transaction() as tx:
        attempt_id = hashlib.sha256(email.encode()).hexdigest()
        attempt = tx.get("login_attempts", attempt_id) or {
            "id": attempt_id,
            "count": 0,
            "start": time.time(),
        }
        if time.time() - attempt["start"] > 300:
            attempt = {"id": attempt_id, "count": 0, "start": time.time()}
        if attempt["count"] >= 10:
            raise HTTPException(429, "Too many attempts; retry in five minutes")
        user = next((u for u in tx.all("users") if u["email"] == email), None)
        expected = user.get("password_hash") if user else None
        valid = expected and hmac.compare_digest(
            password_hash(login.password, expected.split(":")[0]), expected
        )
        if (
            not valid
            or not user.get("active", True)
            or (
                not allow_demo
                and (user.get("demo_account") or email.endswith("@paypool.demo"))
            )
        ):
            attempt["count"] += 1
            tx.put("login_attempts", attempt)
            result = None
        else:
            tx.delete("login_attempts", attempt_id)
            token, csrf = issue_session(tx, user)
            tx.audit(user["id"], "SIGNED_IN", user["id"])
            result = token, csrf, public_user(user)
    if result is None:
        raise HTTPException(401, "Invalid email or password")
    return result
