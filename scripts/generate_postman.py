"""Generate a portable Postman 2.1 collection for a disposable simulator API."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
items = []


def add(name, method, path, body=None, checks=""):
    headers = [{"key": "Content-Type", "value": "application/json"}]
    if method == "POST":
        headers += [
            {"key": "X-CSRF-Token", "value": "{{csrf}}"},
            {"key": "Idempotency-Key", "value": "{{$guid}}"},
        ]
    req = {"method": method, "header": headers, "url": "{{base_url}}" + path}
    if body is not None:
        req["body"] = {
            "mode": "raw",
            "raw": json.dumps(body),
            "options": {"raw": {"language": "json"}},
        }
    items.append(
        {
            "name": name,
            "request": req,
            "event": [
                {
                    "listen": "test",
                    "script": {
                        "type": "text/javascript",
                        "exec": [
                            'pm.test("HTTP 200", () => pm.response.to.have.status(200));',
                            "if (pm.response.code !== 200) { pm.execution.setNextRequest(null); } else {",
                            "const data = pm.response.json();",
                            checks,
                            "}",
                        ],
                    },
                }
            ],
        }
    )


def login(account):
    add(
        f"Sign in: {account}",
        "POST",
        "/api/v1/auth/login",
        {"email": account + "@paypool.demo", "password": "{{demo_password}}"},
        'pm.collectionVariables.set("csrf", data.csrf);',
    )


add(
    "Verify simulator",
    "GET",
    "/api/v1/config",
    checks="""
pm.collectionVariables.set("verified_demo", "no");
pm.test("Only a labelled local simulator is allowed", () => {
  pm.expect(data.demo_mode).to.eql(true);
  pm.expect(data.payment_provider).to.eql("demo");
});
if (!data.demo_mode || data.payment_provider !== "demo") {
  pm.execution.setNextRequest(null);
} else {
  pm.collectionVariables.set("verified_demo", "yes");
  pm.collectionVariables.set("demo_password", data.demo_password);
  pm.collectionVariables.set("dispatch_date", new Date(Date.now()+2*86400000).toISOString().slice(0,10));
}
""",
)
for name, suffix in (("ananya", "a"), ("rahul", "b"), ("meera", "c")):
    login(name)
    if suffix == "a":
        add(
            "Search eligible catalog",
            "GET",
            "/api/v1/catalog/search?brand=Harvest&unit=kg",
            checks='pm.test("Serviceable stock exists", () => pm.expect(data.total).to.be.above(0));',
        )
        add(
            "Interpret a buying request",
            "POST",
            "/api/v1/procurement/discover",
            {
                "message": "30 kg Sona Masoori rice by {{dispatch_date}}, landed price below USD 1.70/kg",
                "currency": "USD",
            },
            'pm.test("Intent needs buyer confirmation", () => pm.expect(data.intent.confirmation_required).to.eql(true));',
        )
    add(
        f"Confirm request: {name}",
        "POST",
        "/api/v1/procurement/requests",
        {
            "product_id": "rice-sona",
            "zone_id": "south-zone",
            "dispatch_date": "{{dispatch_date}}",
            "quantity_min": 30,
            "quantity_max": 30,
            "ceiling_minor": 170,
        },
        f'pm.collectionVariables.set("request_{suffix}", data.id); pm.collectionVariables.set("pool_id", data.pool_id);',
    )

login("seller")
add(
    "Clear the shared agreement",
    "POST",
    "/api/v1/pools/{{pool_id}}/clear",
    {},
    """
pm.test("Three buyers receive exact $48 quotes", () => {
  pm.expect(data.status).to.eql("CLEARED"); pm.expect(data.allocations).to.have.lengthOf(3);
  data.allocations.forEach(a => pm.expect(a.total_minor).to.eql(4800));
}); pm.collectionVariables.set("pool_version", data.version);
""",
)
for name, suffix in (("ananya", "a"), ("rahul", "b"), ("meera", "c")):
    login(name)
    add(
        f"Approve exact allocation: {name}",
        "POST",
        "/api/v1/pools/{{pool_id}}/approve",
        {"version": "{{pool_version}}"},
        f'pm.collectionVariables.set("order_{suffix}", data.id);',
    )
    add(
        f"Create simulated checkout: {name}",
        "POST",
        f"/api/v1/orders/{{{{order_{suffix}}}}}/checkout",
        {},
    )
    add(
        f"Simulate buyer authorization: {name}",
        "POST",
        f"/api/v1/orders/{{{{order_{suffix}}}}}/authorize",
        {},
        'pm.test("Authorization confirmed by simulator", () => pm.expect(data.payment_status).to.eql("AUTHORIZED"));',
    )
login("seller")
add(
    "Dispatch the authorized run",
    "POST",
    "/api/v1/pools/{{pool_id}}/dispatch",
    {"driver_id": "driver-demo", "vehicle_id": "demo-van"},
)
login("driver")
for suffix in ("a", "b", "c"):
    add(
        f"Record delivery evidence: {suffix}",
        "POST",
        f"/api/v1/orders/{{{{order_{suffix}}}}}/pod",
        {
            "delivered_quantity": 30,
            "recipient_name": "Demo shop recipient",
            "acknowledgement": True,
            "exception": None,
            "note": "Postman simulator walkthrough",
        },
        'pm.test("Demo policy captures after complete evidence", () => pm.expect(data.payment_status).to.eql("CAPTURED"));',
    )
login("ananya")
add(
    "Inspect reconciled receipt",
    "GET",
    "/api/v1/orders/{{order_a}}/receipt",
    checks='pm.test("Receipt matches simulation evidence", () => pm.expect(data.status).to.eql("MATCHED"));',
)
add("Sign out", "POST", "/api/v1/auth/logout", {})

collection = {
    "info": {
        "name": "PayPool — disposable simulator walkthrough",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        "description": "Run the entire collection in order against a fresh local demo database. This creates three requests and simulates authorization/delivery/capture. It is not a real PayPal test. No secrets are included; browser-independent login cookies are handled by the collection runner.",
    },
    "variable": [
        {"key": "base_url", "value": "http://127.0.0.1:8200"},
        {"key": "verified_demo", "value": "no"},
    ],
    "event": [
        {
            "listen": "prerequest",
            "script": {
                "type": "text/javascript",
                "exec": [
                    r'const local = /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(pm.variables.get("base_url") || "");',
                    'if (!local || (pm.info.requestName !== "Verify simulator" && pm.collectionVariables.get("verified_demo") !== "yes")) { pm.execution.skipRequest(); throw new Error("Run the full collection against a disposable local simulator only."); }',
                ],
            },
        }
    ],
    "item": items,
}
target = ROOT / "contracts/postman/paypool.postman_collection.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(collection, indent=2, ensure_ascii=False) + "\n")
print(f"Generated {len(items)} requests: {target.relative_to(ROOT)}")
