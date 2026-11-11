"""Explicit offline simulation or genuine PayPal sandbox HTTP calls.

No production host is accepted. Every mutating operation has a stable request
ID derived from its persisted application operation, including retries.
"""

import hashlib
import os
import time
from urllib.parse import quote

import httpx


class PaymentError(Exception):
    pass


def amount(value):
    return f"{value // 100}.{value % 100:02d}"


class Payments:
    def __init__(self, demo=True):
        self.mode = os.getenv(
            "PAYPOOL_PAYMENT_PROVIDER", "demo" if demo else "paypal_sandbox"
        )
        if self.mode not in {"demo", "paypal_sandbox"} or (
            self.mode == "demo" and not demo
        ):
            raise ValueError(
                "Demo payments require demo mode; supported provider: paypal_sandbox"
            )
        self.client_id = os.getenv("PAYPAL_CLIENT_ID", "")
        self.secret = os.getenv("PAYPAL_CLIENT_SECRET", "")
        self.webhook_id = os.getenv("PAYPAL_WEBHOOK_ID", "")
        self.frontend = os.getenv(
            "PAYPOOL_FRONTEND_URL", "http://localhost:3000"
        ).rstrip("/")
        self.base = "https://api-m.sandbox.paypal.com"
        self._token, self._expires = None, 0

    def token(self):
        if not self.client_id or not self.secret:
            raise PaymentError("PayPal sandbox credentials are not configured")
        if not self._token or time.time() >= self._expires:
            try:
                r = httpx.post(
                    self.base + "/v1/oauth2/token",
                    auth=(self.client_id, self.secret),
                    data={"grant_type": "client_credentials"},
                    timeout=20,
                )
                r.raise_for_status()
                data = r.json()
                self._token = data["access_token"]
                self._expires = time.time() + max(0, int(data["expires_in"]) - 60)
            except (httpx.HTTPError, KeyError, ValueError) as e:
                raise PaymentError("Could not authenticate with PayPal sandbox") from e
        return self._token

    def call(self, method, path, operation=None, body=None):
        headers = {
            "Authorization": f"Bearer {self.token()}",
            "Content-Type": "application/json",
        }
        if operation:
            headers["PayPal-Request-Id"] = hashlib.sha256(
                operation.encode()
            ).hexdigest()[:38]
        try:
            r = httpx.request(
                method, self.base + path, headers=headers, json=body, timeout=20
            )
            r.raise_for_status()
            return r.json() if r.content else {}
        except httpx.HTTPStatusError as e:
            # Return the provider's opaque diagnostic identifier, never tokens
            # or request headers. The caller records an uncertain state.
            raise PaymentError(
                f"PayPal sandbox rejected the action (HTTP {e.response.status_code}, debug {e.response.headers.get('paypal-debug-id', 'unavailable')})"
            ) from e
        except (httpx.HTTPError, ValueError) as e:
            raise PaymentError(
                "PayPal response is uncertain; reconcile before continuing"
            ) from e

    def create(self, order):
        if self.mode == "demo":
            return {"id": "DEMO-" + order["id"], "status": "CREATED", "links": []}
        if order["currency"] not in {"USD", "EUR", "GBP"}:
            raise PaymentError(
                "This sandbox flow is configured for USD, EUR or GBP; INR is demo-only"
            )
        ref = quote(order["id"], safe="")
        return self.call(
            "POST",
            "/v2/checkout/orders",
            "checkout:" + order["id"],
            {
                "intent": "AUTHORIZE",
                "purchase_units": [
                    {
                        "reference_id": order["id"],
                        "custom_id": order["id"],
                        "description": "PayPool approved wholesale allocation",
                        "amount": {
                            "currency_code": order["currency"],
                            "value": amount(order["total_minor"]),
                        },
                    }
                ],
                "payment_source": {
                    "paypal": {
                        "experience_context": {
                            "user_action": "CONTINUE",
                            "shipping_preference": "NO_SHIPPING",
                            "return_url": self.frontend
                            + "/retailer/orders?approved="
                            + ref,
                            "cancel_url": self.frontend
                            + "/retailer/orders?cancelled="
                            + ref,
                        }
                    }
                },
            },
        )

    def authorize(self, order):
        if self.mode == "demo":
            return {
                "id": "DEMO-AUTH-" + order["id"],
                "status": "CREATED",
                "amount": {
                    "currency_code": order["currency"],
                    "value": amount(order["total_minor"]),
                },
            }
        remote = self.call("GET", "/v2/checkout/orders/" + order["provider_order_id"])
        if remote.get("status") not in {"APPROVED", "COMPLETED"}:
            raise PaymentError("The buyer has not approved the PayPal order")
        units = remote.get("purchase_units", [])
        if len(units) != 1 or units[0].get("amount") != {
            "currency_code": order["currency"],
            "value": amount(order["total_minor"]),
        }:
            raise PaymentError(
                "PayPal order amount does not match the approved allocation"
            )
        existing = units[0].get("payments", {}).get("authorizations", [])
        result = (
            remote
            if existing
            else self.call(
                "POST",
                "/v2/checkout/orders/" + order["provider_order_id"] + "/authorize",
                "authorize:" + order["id"],
                {},
            )
        )
        auth = result["purchase_units"][0]["payments"]["authorizations"][0]
        if auth["status"] not in {"CREATED", "AUTHORIZED"}:
            raise PaymentError("PayPal authorization is not available for capture")
        return auth

    def capture(self, order):
        if self.mode == "demo":
            return {"id": "DEMO-CAPTURE-" + order["id"], "status": "COMPLETED"}
        return self.call(
            "POST",
            "/v2/payments/authorizations/" + order["authorization_id"] + "/capture",
            "capture:" + order["id"],
            {
                "amount": {
                    "currency_code": order["currency"],
                    "value": amount(order["total_minor"]),
                },
                "final_capture": True,
            },
        )

    def void(self, order):
        if self.mode == "demo":
            return {}
        return self.call(
            "POST",
            "/v2/payments/authorizations/" + order["authorization_id"] + "/void",
            "void:" + order["id"],
            {},
        )

    def refund(self, order, value, operation):
        if self.mode == "demo":
            return {"id": "DEMO-REFUND-" + operation, "status": "COMPLETED"}
        return self.call(
            "POST",
            "/v2/payments/captures/" + order["capture_id"] + "/refund",
            operation,
            {"amount": {"currency_code": order["currency"], "value": amount(value)}},
        )

    def verify_webhook(self, headers, event):
        if self.mode != "paypal_sandbox" or not self.webhook_id:
            raise PaymentError("A sandbox webhook ID must be configured")
        result = self.call(
            "POST",
            "/v1/notifications/verify-webhook-signature",
            body={
                "auth_algo": headers.get("paypal-auth-algo"),
                "cert_url": headers.get("paypal-cert-url"),
                "transmission_id": headers.get("paypal-transmission-id"),
                "transmission_sig": headers.get("paypal-transmission-sig"),
                "transmission_time": headers.get("paypal-transmission-time"),
                "webhook_id": self.webhook_id,
                "webhook_event": event,
            },
        )
        if result.get("verification_status") != "SUCCESS":
            raise PaymentError("Webhook signature verification failed")
