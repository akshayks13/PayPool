# PayPool scope

PayPool is a B2B pooled-purchasing application available at
https://paypool-ai.vercel.app, with source published on `main` at
https://github.com/akshayks13/PayPool. `make dev` starts the
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

## Current payment and deployment verification

- **Local:** `make sandbox` starts the frontend, API and worker using separate
  persistent SQLite data and genuine PayPal Sandbox checkout. `make demo` remains
  an explicitly simulated workflow.
- **Hosted:** Vercel serves the frontend; the API and worker run together in a
  free Docker service under Render's **PayPool / Production** project. Neon
  PostgreSQL stores persistent data. Vercel and Render deploy from GitHub `main`.
- **Verified locally and hosted:** genuine SDK popup, Personal sandbox buyer
  login, approval and $49 server-side authorization, with the parent app staying
  on **My orders**. These checks used fictional sandbox purchases, not real money.
- **Verified hosted:** signature-verified PayPal webhook and persisted receipt
  evidence. Unsigned webhook rejection has also been checked.
- **Focused regression coverage:** popup cancellation/retry, SDK failure with
  full-page fallback, failed authorization never appearing successful, public
  SDK configuration without OAuth secrets, and PayPal amount breakdown handling.
- **Not yet verified end to end against PayPal:** capture after delivery and the
  subsequent real sandbox refund/void lifecycle. The local simulator and automated
  tests cover these application paths; this is separate from real-provider proof.
- PayPal Identity login and native delegated payments remain disabled. Supplier
  access approval is not PayPal partner merchant onboarding.

See [payment flow and verification](payments.md) and [deployment](deployment.md)
for configuration, walkthroughs and service limitations.

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

The hosted Docker service and Neon PostgreSQL have been exercised. Optional
PostGIS and Elasticsearch deployment still need service-specific checks; prior
Redis/Celery checks passed. These optional services are not required by the local
SQLite workflow or the current hosted SQL worker.
