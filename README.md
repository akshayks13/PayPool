# PayPool

Independent shops combine wholesale demand into a viable supplier delivery run.
Each buyer keeps a hard delivered-price limit, approves an exact allocation and
authorizes their own purchase. If someone leaves, PayPool releases old commitments
and requires fresh consent for revised terms.

## Start the app

Requires **Python 3.12+ and Node.js 22+**. From this directory:

```sh
make setup   # first time: installs backend and frontend dependencies
make dev     # starts API, web app and background worker together
```

Open **http://localhost:3000**. API documentation: **http://localhost:8000/docs**.
Stop all three processes with Ctrl+C. After installation, only `make dev` is needed.

For a fresh recording/demo, stop the current run and use `make demo`. It uses a
new, separate database and preserves existing development data. The terminal
prints the retained demo database path. `make dev` uses persistent SQLite at
`backend/data/paypool.db`. Docker, Redis and PostgreSQL are not needed locally.

Select a demo account and click Sign in. Development password: **PayPool-demo-2026!**.
These accounts are refused when demo mode is disabled.

| Account | Role |
| --- | --- |
| ananya@paypool.demo | Retailer / GreenMart |
| rahul@paypool.demo | Retailer / Corner Store |
| meera@paypool.demo | Retailer / Fresh Basket |
| seller@paypool.demo | Supplier / Sree Distributors |
| driver@paypool.demo | Driver / Kiran |
| admin@paypool.demo | Operations administrator |

Use separate browser profiles for multiple roles. Businesses, USD prices and
coordinates are fictional demo fixtures. Payments are explicitly simulated;
no real money moves in demo mode.

## What works

- Business/contact/delivery profiles, notification preferences and protected address changes.
- Supplier application, rejection/correction/resubmission, administrator approval and account disable/reactivation.
- Supplier catalog, tier prices, stock movements, reviewed CSV/XLSX imports and authenticated product-photo uploads.
- Catalog search/facets/pages, saved buying conversations, Gemini-assisted interpretation/explanations, quantity range, preferred target and hard ceiling.
- Buyer/supplier policy recommendations, versioned offers/counters/rejection, comparison and revision history.
- Editable delivery zones/schedules, fleet, capacity/freight clearing and immutable individual approvals.
- Simulated or configured sandbox checkout, durable financial recovery and renewed approval after group changes.
- Assigned driver routes, snapshotted delivery contacts, photo evidence, exceptions/redelivery and buyer confirmation.
- Reconciled printable receipts, notifications, audit search, worker health, ledger and job recovery.

## Optional connections

Server-only settings live in ignored `backend/.env`; start from `.env.example`
only for a new checkout, preserving any existing key file.

**Gemini:** set `GEMINI_API_KEY`, `PAYPOOL_LLM_PROVIDER=gemini` and optionally
`PAYPOOL_GEMINI_MODEL` (default `gemini-2.5-flash`). Without a key, the local default
is explicitly labelled offline interpretation. The team's local key is not in Git.

**PayPal:** current payments are simulated at the team's request. The sandbox
Orders/authorization/capture/void/refund/webhook adapters exist but need actual
account verification. When access is available, set `PAYPOOL_PAYMENT_PROVIDER=paypal_sandbox`,
`PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID` and `PAYPAL_SELLER_ID`.
Use sandbox merchant/buyer accounts and real verified webhook events. Optional
PayPal Login is configured separately through `PAYPAL_LOGIN_ENABLED` and a
registered callback. This build supports one configured merchant, not a pooled
wallet, escrow or automatic multi-merchant payout.

Optional PostgreSQL/PostGIS, Redis/Celery and Elasticsearch configuration is in
`backend/.env.example` and `compose.yaml`. Their local fallback is sufficient for
the demo. Do not treat a configured adapter as a verified deployment.

## Code and checks

```text
frontend/   Next.js / React / TypeScript portal
backend/    FastAPI, SQLAlchemy, domain rules, solver, integrations and workers
contracts/  Current OpenAPI, pinned external-agent schemas and Postman collection
```

Run checks appropriate to changed code:

```sh
(cd backend && .venv/bin/python -m pytest -q tests/test_business.py)
(cd frontend && npm run typecheck)
(cd frontend && npm run test:e2e -- e2e/business.spec.ts)
```

`make test` runs all backend tests plus typechecking. `npm run build` in `frontend`
checks a production build; stop the local frontend first. `make postman-demo`
starts a disposable API and executes the 32-request simulator walkthrough without
changing your working database. It downloads the pinned Newman runner on first use.

Images are authenticated, limited to PNG/JPEG/WebP up to 2 MB and 16 megapixels,
normalized to at most 2048 px, stripped of embedded metadata and stored in SQL.
There is a 100-image limit per account. Internal images are not published in feeds.

## Project notes

- [Current scope and remaining setup](docs/STATUS.md)
- [Architecture](docs/architecture.md)
- [Demo walkthrough](docs/demo.md)
- [Submission description and video plan](docs/hackathon-submission.md)
- [External-agent interface](docs/acp.md)

Historical prompts, audits and prototype screens were removed from the current
tree; Git retains their history. Keep submissions aligned with the actual build.
