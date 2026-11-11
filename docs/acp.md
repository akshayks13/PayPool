# External-agent integration

Checkout schemas are pinned to **ACP 2026-04-17**, upstream commit `17adf494cf8b4bcb41967a0386188b8103316d2f`. The source URLs and SHA-256 digests are recorded in `contracts/acp/2026-04-17/manifest.json`; the upstream Apache license is included. Requests and responses are validated against the vendored JSON Schema.

## Authority

A retailer explicitly provisions temporary, revocable access through `/api/v1/me/agent-access`. Only the token hash is stored. The bearer grants access to that buyer's already approved quote; it cannot create procurement requests, accept offers, grant roles, approve allocations or authorize money.

`ACP_ENABLED=false` is the default. If enabled, requests require `Authorization: Bearer …`, `API-Version: 2026-04-17`, and an `Idempotency-Key` on POST operations. Input shape, currency, SKU, server price, ownership, agreement hash and session expiry are checked. Buyer/order context is derived from the token and approved quote, not an untrusted email claim.

Supported paths: create, retrieve, update, complete and cancel under `/acp/checkout_sessions`. Native delegated payment processing is disabled: the valid protocol response is `requires_escalation` with a PayPool continuation URL. Completion never pretends that a purchase was paid. Cancellation closes the external session and does not silently cancel a shared buying agreement.

The integration uses bearer authentication for requests; protocol Signature/Timestamp parameters are optional and are not presented as a completed bilateral signing/certification deployment. Native agent payment handlers and external order-event delivery need the partner-approved transport/provider configuration before activation.

## Product feed

Supplier feed preparation follows the [official discovery file-upload reference](https://developers.openai.com/commerce/specs/file-upload/products). It reports missing factual merchant fields and exports reviewed JSONL. It uses the base catalog unit price, current SQL availability, and `is_eligible_checkout=false`. It contains no buyer addresses, budgets, tokens or private pool memberships.

A prepared file is not a published feed or a claim of ChatGPT eligibility. Region, shipping, merchant identity and partner ingestion still need the actual merchant's setup.

## Activation

The public protocol is separate from approved distribution/payment access. [PayPal Agent Ready](https://developer.paypal.com/agent-ready/overview/) documents the Braintree delegated-token path. Do not enable an invented handler, accept a purchase-order number as payment proof, or fabricate delegated tokens. Portal PayPal sandbox approval remains the runnable payment path.
