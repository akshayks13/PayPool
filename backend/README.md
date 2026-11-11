# PayPool API and workers

The running domain is `app/platform`: authenticated procurement, supplier
operations, bounded clearing, agreements, payments, fulfillment and reconciliation.
`app/modules/negotiation` contains the typed agent and model-adapter foundation.
This is a modular monolith with SQLAlchemy JSON records and an Alembic baseline;
the original normalized domain-table layout is not implemented.

Use `make setup` and `make dev` from the repository root. For just the API:

```sh
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The default durable store is SQLite. PostgreSQL records and Redis/Celery have
separate service checks; PostGIS and Elasticsearch adapters require configured
services and are not represented as verified deployments. The normal SQL outbox
worker needs no Redis. Use `make worker` or the Celery command in the root README.

## Gemini

Set `GEMINI_API_KEY`, `PAYPOOL_LLM_PROVIDER=gemini`, and optionally
`PAYPOOL_GEMINI_MODEL` (code default: `gemini-2.5-flash`) in the ignored
`backend/.env`. Actual extraction, explanation and embedding calls have been
checked with the team's key; no key is included in source or tests.

The portal calls `POST /api/v1/procurement/discover`. The simpler
`POST /api/v1/procurement/parse` returns a validated intent only. Parsing never
creates a buying request, approves a quote or authorizes a payment. Typed agent
advice and commercial proposals are distinct from final clearing and consent.

`PAYPOOL_LLM_TIMEOUT_MS` defaults to 20,000 ms. Transient provider/network failures
use bounded backoff through `PAYPOOL_LLM_MAX_RETRIES` (default 2) and
`PAYPOOL_LLM_RETRY_BACKOFF_MS` (default 500). Authentication, quota, model and schema
failures are not retried. `PAYPOOL_LLM_PROVIDER=deterministic` is explicitly offline.

Historical fixture/agent-demo routes are opt-in and require both demo mode
and `PAYPOOL_ENABLE_LEGACY_API=true`. They are not the normal portal API.

## Payments and scope

PayPal Orders authorization/capture/void/refund, webhook verification and
reconciliation adapters exist. The current runtime uses the labelled simulator
because sandbox registration/credentials are unavailable. A real PayPal
transaction and PayPal Identity round trip remain unverified.

See the [root README](../README.md) for setup, accounts and integration variables,
[delivery status](../docs/STATUS.md) for open work, and `/docs` on the running API
for actual contracts.
