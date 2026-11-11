# PayPool

Independent shops combine compatible wholesale demand into one delivery run. Each buyer keeps their own price limit, approves their exact allocation, and authorizes their own payment. A withdrawal triggers a new agreement and fresh consent.

This repository includes a working multi-role portal and persistent procurement API. Read [delivery status](docs/STATUS.md) for the authoritative completion report, [implementation status](docs/implementation.md) for feature/test details and [demo walkthrough](docs/demo.md) for a presentation script.

For submission requirements, the draft description and a timed video plan, see [hackathon submission](docs/hackathon-submission.md). Real Gemini extraction/narration have been verified; PayPal payments currently run in explicitly labelled simulation mode pending sandbox access.

## Run locally

Requires Python 3.12+ and Node 22+.

```sh
make setup
make dev
```

`make dev` starts the API, portal and durable worker. Stop all three with Ctrl+C. For separate terminals use `make backend`, `make frontend`, and `make worker`. `make migrate` applies the schema history without deleting existing records.

Open **http://localhost:3000**. API documentation: **http://localhost:8000/docs**.

Defaults: persistent SQLite at `backend/data/paypool.db`, fictional businesses and prices, explicitly labelled offline parsing, simulated payments. No API keys required. Restarting servers preserves sessions and orders. Use a separate `DATABASE_URL` for a fresh demonstration; do not delete a database containing unresolved sandbox payments.

Select a demo account on the login screen, then click **Sign in**. Shared development password: `PayPool-demo-2026!`.

| Account | Role |
| --- | --- |
| ananya@paypool.demo | Retailer · GreenMart |
| rahul@paypool.demo | Retailer · Corner Store |
| meera@paypool.demo | Retailer · Fresh Basket |
| seller@paypool.demo | Sree Distributors |
| driver@paypool.demo | Delivery driver |
| admin@paypool.demo | Operations |

Use separate browser profiles/incognito contexts for several signed-in users. Coordinates are in Bengaluru; USD prices are **fictional sandbox fixtures**, not Indian market quotations.

## Real integrations

Copy `backend/.env.example` to `backend/.env` to change configuration. Secrets stay server-side and are ignored by Git. Frontend `API_BASE_URL` controls its same-origin `/api` proxy.

**Gemini:** set `GEMINI_API_KEY`, an account-accessible `PAYPOOL_GEMINI_MODEL`, and `PAYPOOL_LLM_PROVIDER=gemini`. Structured extraction and narration use persisted catalog facts. Provider failures are visible. Offline mode is explicitly identified and does not impersonate a model call.

**PayPal sandbox:** set `PAYPOOL_PAYMENT_PROVIDER=paypal_sandbox`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, and `PAYPAL_SELLER_ID` to the PayPool distributor receiving funds (`seller-demo` for the seeded demo). Buyers approve on PayPal; the API authorizes the exact agreed amount and captures after complete acknowledged delivery. This build supports **one configured sandbox merchant**, with separate purchases per buyer. It provides no pooled wallet or escrow.

Register an HTTPS webhook at `/api/v1/webhooks/paypal`, set `PAYPAL_WEBHOOK_ID`, and subscribe to authorization/capture/refund events. Events are signature-verified through PayPal, deduplicated and reconciled against provider reads. PayPal's mock webhook simulator does not support this postback-verification path; use events from sandbox purchases. See [authorization/capture](https://developer.paypal.com/docs/checkout/standard/customize/authorization/) and [webhook integration](https://developer.paypal.com/api/rest/webhooks/rest/).

**PayPal Login:** separately enable Identity access, register `http://localhost:3000/api/v1/auth/paypal/callback`, and set `PAYPAL_LOGIN_ENABLED=true`. New identities start as retailers; admins grant other roles. Login uses the authorization-code exchange, authenticated userinfo, browser-bound state and stable provider subject. See [PayPal Login setup](https://developer.paypal.com/docs/log-in-with-paypal/integrate/).

**PostgreSQL/PostGIS:** set `DATABASE_URL=postgresql://...` and optionally `PAYPOOL_POSTGIS=true` for indexed `ST_Covers` eligibility. SQLite uses a tested boundary-inclusive geometry fallback. Optional `docker compose up --build` starts a local PostGIS stack; the container path has not been exercised in the current environment.

For an unseeded sandbox environment set `PAYPOOL_DEMO_MODE=false`, `PAYPOOL_PAYMENT_PROVIDER=paypal_sandbox`, and `PAYPOOL_COOKIE_SECURE=true` behind HTTPS. Demo accounts and sessions are refused outside demo mode. Bootstrap accounts privately:

```sh
cd backend
.venv/bin/python -m app.platform.accounts --email ops@example.com --name "Operations" --role ADMIN
```

Passwords are prompted privately. Use `--role SELLER --verified --lon ... --lat ...` for a distributor and set `PAYPAL_SELLER_ID` to the returned ID. This is a local operator tool, not a public role-grant endpoint.

## Checks

```sh
make test
cd frontend
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser tests start isolated API/portal servers with a temporary database. API tests cover ceilings, freight rounding, dropout recovery, payment states, delivery exceptions, refunds, persistence and access control.

## Full application workflow

- Retailers: natural-language discovery, confirmed requests, versioned supplier offers/counters, recurring instructions, final quotes, individual authorization, buyer receipt confirmation and printable reconciliation records.
- Suppliers: reviewed catalog imports, variants/metadata, stock movement history, pricing floors, editable map boundaries, weekly schedules/cutoffs, configurable freight allocation, fleet and dispatch.
- Drivers: assigned stop order/navigation, delivery evidence, exceptions and preserved redelivery attempts.
- Operations: persisted audit/notifications, role grants, seller verification, durable event queue, retry diagnostics, payment activity and worker health.
- External agents: revocable buyer-scoped access, pinned ACP 2026-04-17 continuation sessions and prepared JSONL discovery feeds. Tokenized native payment completion stays disabled without eligible merchant access.

A product's base catalog price is used for public feed preparation; an unearned bulk discount is never advertised as an individual purchase price. Missing public product/image details are reported instead of fabricated.

## Workers and optional services

The default worker uses the SQL outbox and needs no Redis. For Celery:

```sh
cd backend
.venv/bin/python -m celery -A app.platform.tasks worker --beat --loglevel=INFO
```

Configure `REDIS_URL`. Optional Elastic retrieval uses `ELASTICSEARCH_URL`; `PAYPOOL_EMBEDDINGS_ENABLED=true` adds 768-dimensional Gemini embeddings and reciprocal rank fusion. SQL revalidates stock, ownership, serviceability and final prices. Outbox jobs index catalog changes. Provider failures visibly use the keyword fallback.

`ACP_ENABLED=false` is the default. Enabling it exposes a constrained continuation API, not native agent payment processing. Read [ACP integration](docs/acp.md), [prompt coverage](docs/prompt-coverage.md), and [product decisions](docs/product-decisions.md).

## Design boundaries

- Money is integer minor units. Seller prices must include tax; the delivered total adds disclosed freight. There is no separate tax or provider-fee engine.
- Bounded OR-Tools manifest search allows six buyers, integer catalog units and 30,000 candidates. Every integer quantity in the approved interval is searched. A larger search is rejected explicitly; this is not an unbounded or continuous optimizer.
- Stop sequencing uses geographic distance, not road traffic or live ETAs.
- Buyer/supplier agents are application policy roles with optional Gemini assistance. Independent distributed agent workers are not deployed.
- Native delegated payments, vaulting, multi-merchant onboarding and live payments are disabled. The ACP continuation API is also off by default. [Delivery status](docs/STATUS.md) distinguishes implemented features, unverified integrations and remaining work.

```text
frontend/    Next.js portal, authenticated API client, browser tests
backend/     FastAPI, solver, persistence, PayPal adapters, API tests
contracts/   Current OpenAPI snapshot and pinned ACP schemas
docs/        Product vision, current status and demo
```
