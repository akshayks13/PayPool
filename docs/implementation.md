# PayPool implementation status

PayPool combines distributor-led B2B procurement with explicit buyer agreements, hard delivered-price limits, independent payments and recovery. The current executable domain is `backend/app/platform`, consumed by the four-role Next.js portal.

## Running application

| Area | Behavior |
| --- | --- |
| Identity | Hashed passwords, persistent sessions, HttpOnly cookies, CSRF/origin checks, account lockout, server roles/ownership, expiry handling and no-role onboarding; optional PayPal authorization-code/userinfo login |
| Catalog | Product metadata/variants, base and volume tiers, negotiation floors, create/edit/archive, CSV/XLSX review/commit, stock movements with expected-balance checks |
| Discovery | SQL-scoped serviceable catalog and category filters, protected specification/pack matching, optional Elastic lexical/vector retrieval with explicit keyword fallback; optional Gemini extraction/narration |
| Negotiation | Persisted two-party offers, counters, expiry/version checks, actor validation, idempotent initial proposals, revision history, seller floors and buyer ceilings; accepted terms enter final clearing |
| Recurrence | Revocable standing buying instructions, per-date occurrence deduplication, specification revalidation, review-required failures; never automatic purchase consent |
| Delivery areas | Leaflet vertex drawing/dragging plus coordinate editor, validated polygons, weekdays/timezone/windows, cutoffs, automatic clearing policy and buyer-confirmation policy |
| Clearing | Transactional lock/optimization states, complete integer quantity search within the explicit candidate cap, stock/tier/capacity/zone checks, configurable normalized weight/volume freight, exact-cent rounding and independent validation |
| Agreements | Versioned allocation records with product, buyer, location, delivery-zone, expiry and price snapshots; deterministic order IDs and hashes |
| Recovery | Persist old cancellation before revised clearing; void holds, exclude withdrawn demand and require renewed consent; preserve failed replacement state and completed financial actions |
| Fleet | Vehicle records/capacity, driver and vehicle availability checks, immutable dispatch snapshot, ordered manifest and navigation |
| Stock | Cleared reservations protect future allocations; dispatch commits physical stock once; declared saleable returns/replacements create audited movements |
| Delivery | Assigned-driver append-only evidence, exceptions and preserved attempt history; live capture requires authenticated buyer confirmation; exception cancellation/redelivery cannot increase the agreed total |
| Payments | Explicit simulator or single-merchant PayPal sandbox create/authorize/capture/void/refund; persisted operation intent before external calls, conflicting-operation guards, stable provider IDs, uncertain-state reconciliation |
| Webhooks | Signature verification outside the event loop, durable normalized event records, deduplication, capture/refund reference recovery and provider re-reads; pending events survive provider outages |
| Receipts | Current reconciliation JSON, persisted worker projections and printable HTML; proof/confirmation/payment match, snapshotted terms, masked print references, refund state and simulation label |
| Background jobs | Transactional outbox, replay-safe projections, retries/dead letters, worker heartbeat, recurring/cutoff/expiry scheduler, capture/reconciliation recovery; standalone SQL worker or Redis/Celery executor |
| Operations | Account-scoped notifications, audit, seller verification and role grants, payment activity ledger, queue health and controlled retries |
| External agents | Buyer-scoped revocable credentials, upstream-pinned ACP 2026-04-17 create/retrieve/update/complete/cancel contract, exact approved-quote binding, idempotency and expiry; safe portal continuation without delegated payment access |
| Feed preparation | Merchant-reviewed JSONL using factual product details, base catalog price and current availability; reports missing required content, never publishes automatically or enables native checkout |
| Persistence | SQLite or PostgreSQL SQLAlchemy domain records, cross-worker transaction serialization, Alembic baseline preserving existing records; optional indexed PostGIS `ST_Covers` |

## Checks performed

- 62 default backend tests pass; the two optional service checks are skipped without disposable service URLs.
- Both optional checks were run successfully against local PostgreSQL 14 and Redis/Celery, including after the framework security updates: complete fulfillment/reconciliation and actual broker-to-worker consumption.
- Five browser journeys cover the successful order, dropout recovery, scoped copilot access, commercial offers/fleet/stock, and map/recurrence/buyer-confirmation/worker controls.
- TypeScript checks and production compilation pass. npm reported zero known frontend vulnerabilities; pip-audit checked 98 installed Python packages with zero known vulnerabilities after the framework/tooling security updates.
- Alembic preservation, Compose configuration and development-script syntax are checked. Container execution and actual PostGIS extension queries have not been exercised; the local PostgreSQL installation has no PostGIS extension.

## Explicit boundaries

- Six requests/buyers per run, one catalog SKU per request and a 30,000-manifest search budget. Larger integer ranges are rejected explicitly. Routing uses geographic distances, not live road ETAs. A single vehicle fulfills each pool.
- Seller prices include applicable tax. Separate jurisdictional tax calculation, platform fees, partial-delivery capture and automated chargeback adjudication are not claimed. Exceptions support void/close, redelivery and merchant refunds, with explicit stock movements.
- Domain records use a generic SQL JSON table with immutable IDs and snapshots. A normalized enterprise schema, large-scale load certification, managed backups and deployment operations remain rollout work.
- In-process buyer/supplier policies and optional Gemini assistance are implemented. External autonomous runtime deployment and unsupported sponsor integrations are not fabricated.
- **No team credentials were supplied.** Real PayPal sandbox approval/capture/refund/webhooks, Identity and model/embedding calls still require verification with the team's accounts. Their adapters are covered by mocks and fail closed on uncertain outcomes.
- **Delegated/native agent payments, Vault, live payments and partner multi-merchant onboarding remain disabled.** ACP completion returns a validated continuation state; a purchase order is never accepted as proof of payment. This is a deliberate access boundary, not a hidden mock.
- Optional Elastic/PostGIS/Docker paths need their configured services. The no-key SQLite application, SQL worker, PostgreSQL records and Redis/Celery paths are runnable and tested as noted above.

See [prompt coverage](prompt-coverage.md), [combined product decisions](product-decisions.md), [ACP](acp.md) and [demo walkthrough](demo.md).
