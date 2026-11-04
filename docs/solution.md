# PayPool — Product Solution
**Version:** 1.0 | **Status:** Hackathon MVP blueprint

## Overview
PayPool is an AI-powered B2B procurement platform connecting independent retailers with regional wholesale distributors. Retailers describe purchasing needs in natural language or use a guided catalog. Buyer and distributor agents negotiate structured commercial offers; the platform pools compatible demand within a distributor's service area, allocates freight transparently, and checks every allocation against a hard landed-price ceiling. Retailers explicitly approve final orders before checkout. Distributors fulfill pooled deliveries, drivers record proof of delivery (POD), and PayPool generates auditable Smart Receipts.

The primary product is a multi-role web portal. An Agentic Commerce Protocol (ACP) adapter is an additional channel for external AI shopping surfaces; it reuses PayPool's authoritative catalog, pricing, inventory, order, and fulfillment services.

## Problem
**Retailers:** wholesale minimum order quantities are too large, small orders attract disproportionate delivery costs, and final landed cost is difficult to compare before purchase.
**Distributors:** vehicles leave underfilled, sparse orders increase route costs, demand can exceed fleet capacity, and dispatch/payment reconciliation is fragmented.

## Core invariant
For every retailer and SKU: landed unit cost = negotiated wholesale unit price + allocated freight per unit. An allocation may clear only when landed unit cost is less than or equal to that retailer's hard ceiling (C_max). The ceiling is an immutable business rule enforced by deterministic code, never by an LLM.

## Roles
- RETAILER: business profile, delivery location, natural-language procurement, price ceiling, offer/pool review, explicit purchase approval, order tracking, receipts.
- SELLER: company profile, catalog, stock, volume tiers, service zones, vehicle capacity, pool review, dispatch.
- DRIVER: assigned route and stops, delivered quantities, recipient confirmation, POD and exceptions.
- ADMIN: role grants, seller verification, moderation, exceptions, payment configuration and audit.

## Retailer journey
1. Sign in with PayPal Identity (OAuth 2.0/OIDC); link the identity to an internal PayPool user.
2. Internal RBAC membership grants roles. PayPal identity never grants a PayPool role by itself.
3. Confirm business profile and delivery location.
4. Enter a request such as: 30 kg Sona Masoori rice by Friday, landed price below ₹52/kg; equivalent brands allowed but rice variety unchanged.
5. AI extracts product, specification, quantity, date, location, target price, hard ceiling and substitution permissions. Retailer confirms or edits the structured request.
6. Geo eligibility filters distributors; hybrid catalog search returns matching SKUs.
7. Buyer and seller agents exchange structured offers and counters within configured limits.
8. Compatible demand joins a single-distributor pool. Freight and landed cost are shown as estimates until locked.
9. At cutoff, deterministic clearing and OR-Tools enforce stock, quantity, vehicle weight/volume, route threshold, serviceability and C_max.
10. Retailer reviews exact final amounts and explicitly approves. Only then does checkout begin.
11. Seller dispatches; driver records POD or an exception; payment events and POD are reconciled into a Smart Receipt.

## Seller and driver journeys
Seller creates catalog variants, stock, weight/volume attributes, price tiers, service polygons, schedules, route fees and vehicle constraints. Seller reviews pool demand and proposed allocations, approves pricing policies, then dispatches cleared orders. Driver sees only assigned stops, records delivered quantities and recipient acknowledgement, and records damaged/missing/refused/unavailable exceptions rather than falsely marking complete.

## Main capabilities
- Conversational procurement and AI-assisted shopping with structured confirmation.
- Commercial negotiation between internal buyer and distributor yield agents.
- Hybrid keyword/vector catalog search and retailer-approved substitution.
- PostGIS service-zone eligibility.
- Geographic demand pooling and normalized weight/volume freight allocation.
- Deterministic cascade clearing and OR-Tools optimization.
- PayPal Login, portal Checkout/Orders adapter, verified webhooks and reconciliation.
- Separate ACP adapter for external agent commerce.
- Dispatch, POD, exceptions, notifications and Smart Receipts.
- Mandatory RBAC and audit trail.

## ACP distinction
ACP is the protocol boundary for external AI agents to discover products and initiate checkout. It is not PayPool's commercial negotiation algorithm. Internal buyer/seller agents negotiate prices and quantities. The web portal copilot does not need ACP simply because it uses natural language. ACP stays behind a feature flag until the exact spec version, merchant onboarding and payment access are confirmed.

## MVP scope
**Must have:** PayPal sandbox login and internal account linking; RBAC; retailer copilot and catalog; seller catalog/inventory; geofence eligibility; structured offers; single-distributor pools; freight apportionment; hard ceiling enforcement; deterministic optimization; explicit approval; sandbox checkout; order tracking; driver POD; Smart Receipt; audit and webhook processing.
**Should have:** semantic substitute ranking with consent, seller yield recommendations, live pool updates, ACP feed/checkout adapter subject to access, invoice/reconciliation exports.
**Later:** multi-distributor pools, autonomous standing orders, complex recurring payments, production marketplace split settlement, ERP integration and advanced forecasting.

## Safety and payment boundaries
- Agents cannot change C_max, grant roles, approve purchases, capture payments or mutate seller inventory directly.
- Never treat PayPal Login as payment approval, PayPal Invoicing as checkout API, or authorization as escrow.
- Verify webhook signatures and deduplicate event IDs; redirects alone do not prove payment.
- Do not store PAN/CVV, client secrets or raw delegated payment tokens.
- PayPal Agent Ready ACP path uses delegated payment tokens through Braintree only if access is approved.
- PayPal India states Indian accounts cannot receive domestic payments from Indian customers. Use sandbox for the hackathon and validate an India-supported provider for live domestic INR transactions.
- Do not assume Payouts, PPCP, Vault, multi-capture, Store Sync or Agent Ready access is available without account/product eligibility.

## Success measures
Request-to-valid-intent rate; time to comparable offers; pool fill and vehicle utilization; percentage of allocations satisfying C_max; freight per unit versus unpooled baseline; retailer approval/cancellation; delivery completion/exceptions; payment reconciliation; receipt completeness.

## References
- https://developer.paypal.com/revenue
- https://developer.paypal.com/agent-ready/overview/
- https://developer.paypal.com/agentic-commerce-services/about/
- https://developer.paypal.com/log-in/how-it-works/
- https://developers.openai.com/commerce
- https://developers.openai.com/commerce/specs/checkout
- https://www.paypal.com/in/cshelp/article/can-i-use-paypal-to-receive-payments-from-indian-customers-help1049