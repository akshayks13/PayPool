# PayPool scope

PayPool is a working local B2B pooled-purchasing application. `make dev` starts the
Next.js portal, FastAPI backend and durable SQL worker. `make demo` starts the same
system with a separate fresh database and explicitly simulated payments.

## Implemented

Business/contact/address/delivery profiles; notification preferences; supplier
applications with review notes, rejection/resubmission and approval; administrative
account activation; catalog/imports/stock/tiers and product photos; catalog facets;
saved copilot tasks; soft target and hard price ceiling; restricted buyer/supplier
policies; commercial offers/counters/rejection and comparison; zones/schedules,
fleet, bounded clearing, private exact approvals and change recovery; driver
contacts/photo evidence, exceptions/redelivery and buyer confirmation; printable
receipts; audit/notifications; durable workers and recovery.

Address changes are blocked during active buying requests. Accepted agreements
retain their delivery-contact snapshots. Notification preferences affect routine
updates; payment/security/application decisions remain available. Supplier approval
grants PayPool access, not PayPal merchant onboarding. Account disabling refuses
unresolved work and revokes existing sessions. Photos are authenticated and
product/order scoped.

Gemini extraction, explanations and embeddings have passed real provider calls.
Current money movement remains simulated, as requested by the team. PayPal API
adapters are implemented but real sandbox and Identity verification are outstanding.

## Required before final hackathon submission

1. Verify actual PayPal sandbox use with team credentials when registration is available.
2. Publish the final source revision publicly with its MIT license; the last anonymous repository check returned 404. Local commits have not been pushed.
3. Record/upload the public video below three minutes and submit the Devpost entry.

The mock can demonstrate the workflow, but does not demonstrate a real PayPal
transaction. Repository run instructions can provide judge access; hosting is optional.

## Deliberate product bounds

Six buyers per run; one SKU per buying request; one vehicle per run; whole selling
units; at most 30,000 candidate manifests. Prices include supplier tax; no separate
jurisdictional tax/fee engine. Geographic routing has no live road ETA. Storage uses
versioned SQL JSON records rather than the original normalized enterprise schema.

The original PDF's autonomous financial consent, similarity-based automatic
substitution and escrow claims were replaced with explicit approval and
independent deterministic validation. Seasonal forecasting, live tracking,
external catalog/ERP synchronization, native delegated payments, Vault, partner
multi-merchant payouts and production operations are future expansions, not
necessary dependencies of the local purchasing workflow and not claimed as built.

PostGIS/Elasticsearch/container deployment still needs real service checks. Prior
PostgreSQL-record and Redis/Celery checks passed. These optional services are not
required by the local SQLite demo.
