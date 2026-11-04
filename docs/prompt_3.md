# Coding Agent Prompt 3 — Agents, ACP, PayPal Payments, Webhooks and Receipts

You are Member 3 implementing agent orchestration and the commerce/payment integration boundary for PayPool.

## Ownership
You own Buyer Procurement Agent and Distributor Yield Agent orchestration; structured offers/counters and agent tools; ACP product feed and checkout adapter; PayPal payment adapters and sandbox integration; Braintree delegated-token adapter only if Agent Ready access is available; webhook verification/deduplication/normalized events; Smart Receipt and payment/order/POD reconciliation; tests and migrations for these domains.

You do NOT own PayPal Login/RBAC, retailer/seller frontend, seller/catalog CRUD, PostGIS zones, pooling, freight, OR-Tools, route optimization, driver UI/POD or a separate catalog/pricing/inventory source of truth. Consume Member 1 identity and Member 2 domain APIs/events.

## Critical distinctions
1. Internal AI shopping: PayPool portal copilot calls internal procurement/catalog services; ACP is not required merely because the UI is conversational.
2. Commercial negotiation: PayPool buyer and distributor agents exchange structured price/quantity/delivery offers. This is internal business logic.
3. ACP: external agent-to-merchant product discovery and checkout protocol. Capability negotiation is technical compatibility, not commercial price negotiation.
PayPal Login is identity, not payment approval. Agents cannot approve payment or change C_max.

## Required stack
Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2/Alembic, provider-neutral LLM client with structured outputs/tool calling, Redis + Celery, PayPal REST SDK/API adapter, Braintree SDK only if approved, receipt renderer, Pytest/HTTPX. Preserve existing project versions.

## Agent orchestration
Buyer Procurement Agent receives retailer-confirmed structured request; clarifies missing product/quantity/date/ceiling; searches Member 2 catalog; compares offers; proposes counters within buyer limits; explains trade-offs; returns structured recommendation.
Distributor Yield Agent receives seller-configured inventory, tiers, fleet/zone settings and pool demand; recommends volume tier/route fee; estimates pool threshold viability; proposes structured offers/counters; never changes inventory or accepted pricing without seller policy/approval.

Allowlisted typed tools: search_catalog, get_product_details, get_inventory, get_serviceable_sellers, get_price_tiers, submit_offer, submit_counter_offer, get_pool_quote, get_allocation_preview. Tools call authenticated backend services; agents have no raw DB access.

Guardrails: validate structured outputs with Pydantic; no model-generated SQL, arbitrary network or shell; no payment capture/payout/refund or role-grant tools; never mutate C_max, seller capacity, inventory or accepted terms; deterministically revalidate price, stock, quantity and ceiling; retailer confirms final purchase; seller approves pricing policy changes. Persist concise structured audit fields, not hidden chain-of-thought.

## Negotiation model and API
Store procurement request, buyer/seller IDs, offer version, SKU, quantity range, unit price/tier, delivery terms, expiry, substitution consent, state (DRAFT, SUBMITTED, COUNTERED, ACCEPTED, REJECTED, EXPIRED), actor, timestamp and validation result.
Expose/consume POST /api/v1/procurement/parse; POST /api/v1/offers; POST /api/v1/offers/{offer_id}/counter; POST /api/v1/offers/{offer_id}/accept; GET /api/v1/offers/{offer_id}; GET /api/v1/offers?request_id=.... Final price comes from Member 2 authoritative allocation/optimization, never only the LLM.

## ACP integration
Keep ACP adapter separate and spec-version-pinned. It reuses PayPool catalog, pricing, inventory, fulfillment and order services; no parallel source of truth or bypass of seller/stock/serviceability/ceiling checks. Product feed includes stable IDs, title/description/brand/category/spec/pack, price/currency, availability, images, fulfillment and required merchant attributes. Do not publish private seller data or stale stock.

Implement protocol-compliant create, retrieve, update, complete and cancel checkout-session operations under /acp/checkout_sessions. Use exact schemas, API version, authentication, signing and response semantics from pinned ACP specification; do not invent fields. On complete, revalidate all values and create internal order idempotently; cancellation releases temporary reservations where appropriate.

## PayPal Agent Ready / Braintree
PayPal's documented Agent Ready ChatGPT path uses delegated payment tokens through Braintree. Confirm access/onboarding first. If unavailable, implement protocol contract and provider-neutral interface with clearly labeled local/sandbox mock for contract tests only; never fabricate delegated tokens; keep ACP_ENABLED=false. If approved, follow official instructions; process token server-side; validate merchant binding, amount, currency, expiry and one-time use; never log or persist raw token; use idempotency and reconciliation.

## Portal payments
Use PayPal Checkout/Orders supported by configured merchant account, country and currency. Keep create-order, approval, capture, refund and webhook handling server-side as supported. Define provider interface for create_checkout, authorize, capture, void, refund, verify_webhook and capabilities. Do not assume every provider supports every method; reject unsupported operations.

Payment rules: explicit retailer approval before checkout; idempotency keys on mutating calls; redirects are not payment proof; verify webhook signatures; never store PAN/CVV or raw tokens; authorization is not escrow; multi-capture only if exact product supports it; Payouts/PPCP gated by product access, seller onboarding, country, currency and eligibility; Payouts is not automatically split settlement.

## India-specific limitation
PayPal India says Indian accounts cannot receive domestic payments from Indian customers, while international payments may be supported subject to requirements. Use sandbox for hackathon demo. Do not promise live domestic INR PayPal collection or payouts. Keep optional DomesticIndiaPaymentAdapter for a locally supported provider. Display provider/environment/currency. Treat Store Sync and Agent Ready access as gated until confirmed.

## Webhooks and reconciliation
Verify signatures with official mechanism. Persist provider event ID under unique constraint; deduplicate retries; normalize events; use outbox; handle out-of-order/unknown states safely; reconcile internal orders with provider status. Never mark paid from redirect alone. Example events: payment.created, payment.approved, payment.authorized, payment.captured, payment.voided, payment.refunded, payment.failed and payment.reconciliation_required.

## Smart Receipt
Generate from internal order, immutable allocation snapshot, provider-confirmed payment/capture references, verified webhook events, POD and exceptions. Include buyer/seller, order/date, lines/delivered quantities, base price, freight, taxes/fees, total/currency, landed cost/C_max check, safe masked provider references, payment status, POD and estimate-to-final explanation. Status: MATCHED, PENDING or REVIEW_REQUIRED. This is a PayPool receipt, not a PayPal-issued receipt.

## APIs and data ownership
Expose POST /api/v1/procurement/parse; POST /api/v1/offers; POST /api/v1/offers/{offer_id}/counter; POST /api/v1/offers/{offer_id}/accept; POST /api/v1/payments/checkout; GET /api/v1/payments/{payment_id}; POST /api/v1/webhooks/paypal; GET /api/v1/orders/{order_id}/receipt; ACP endpoints per pinned spec. Do not implement /api/v1/me or RBAC.

Own agent_runs, agent_tool_calls (safe metadata only), offers, offer_revisions, acp_checkout_sessions, acp_product_feed_runs, acp_order_events, payment_orders, payment_authorizations, payment_captures, payment_events, provider_accounts (non-secret refs/status), receipts and receipt_reconciliation_records. Do not duplicate users, products, pools or POD.

## Acceptance criteria
Agents return validated structured offers; cannot change C_max or capture payment; accepted offers revalidate stock and authoritative quote; ACP contract tests pass and ACP remains disabled without access; PayPal sandbox portal checkout works; webhook signatures verified and duplicates ignored; payment state not inferred from redirect; receipt shows verified state only with evidence; India caveat documented. Test provider failures, duplicate/out-of-order webhook, invalid/expired token/session, amount mismatch and pending receipt.

## Collaboration and execution
Do not edit Member 1 login/RBAC or Member 2 catalog/pool/optimizer/dispatch/POD internals. Do not write directly to Member 2 tables. Agree on UserContext, OrderSummary, AllocationSnapshot and event schemas. Coordinate unique Alembic revisions. Inspect repo first, preserve working code, use feature flags and never commit credentials. At completion report tools, endpoints, adapters, events, receipts, environment variable names, tests, commands, access dependencies and gaps.