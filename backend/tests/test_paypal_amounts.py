"""Regression coverage for genuine PayPal responses with optional breakdowns."""

import pytest

from app.platform import service
from app.platform.payment_execution import DetachedWrites
from app.platform.payments import PaymentError, Payments, amount_matches


@pytest.mark.parametrize(
    "money,expected",
    [
        ({"currency_code": "USD", "value": "49.00", "breakdown": {}}, True),
        ({"currency_code": "USD", "value": "49.01", "breakdown": {}}, False),
        ({"currency_code": "EUR", "value": "49.00"}, False),
        ({"currency_code": "USD"}, False),
        (None, False),
    ],
)
def test_amount_validation_checks_total_and_currency(money, expected):
    assert amount_matches(money, "USD", 4900) is expected


def test_approved_paypal_order_with_breakdown_authorizes_and_reconciles(monkeypatch):
    monkeypatch.setenv("PAYPOOL_PAYMENT_PROVIDER", "paypal_sandbox")
    provider = Payments()
    order = {
        "id": "local-order",
        "provider_order_id": "paypal-order",
        "currency": "USD",
        "total_minor": 4900,
        "payment_status": "CREATED",
    }
    money = {"currency_code": "USD", "value": "49.00", "breakdown": {}}
    auth = {"id": "paypal-auth", "status": "CREATED", "amount": money}
    remote = {
        "id": "paypal-order",
        "status": "APPROVED",
        "purchase_units": [{"amount": money}],
    }
    calls = []

    def call(method, path, *args, **kwargs):
        calls.append((method, path))
        if path == "/v2/payments/authorizations/paypal-auth":
            return auth
        if method == "POST":
            return {"purchase_units": [{"payments": {"authorizations": [auth]}}]}
        return remote

    monkeypatch.setattr(provider, "call", call)
    assert provider.authorize(order) == auth
    assert ("POST", "/v2/checkout/orders/paypal-order/authorize") in calls
    remote["purchase_units"][0]["payments"] = {"authorizations": [auth]}
    result = service.reconcile(DetachedWrites([]), order, provider)
    assert result["payment_status"] == "AUTHORIZED"
    assert result["authorization_id"] == "paypal-auth"
    remote["purchase_units"][0]["amount"] = {**money, "value": "50.00"}
    with pytest.raises(PaymentError, match="does not match"):
        provider.authorize(order)
