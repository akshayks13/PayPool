# Coding Agent Prompt 1 — Identity, RBAC and Retailer Web Experience

> Original specification, retained for traceability. Current delivery and open work: [STATUS.md](STATUS.md). This file is not a completion report.

You are Member 1 implementing the identity/RBAC foundation and retailer-facing experience for PayPool.

## Ownership
You own PayPal Login UI and internal identity/RBAC; shared authenticated shell/navigation and role-aware route protection; retailer frontend pages; frontend API client/types; identity and retailer UI tests.

You do NOT own seller/catalog backend, geospatial eligibility, pooling, freight, OR-Tools, dispatch, POD, agent orchestration internals, ACP endpoints, payment/checkout/webhooks or receipt reconciliation. Consume those services through shared contracts; do not duplicate them.

## Product context
PayPool is a B2B wholesale procurement platform. Retailers shop naturally or through a catalog, set quantity and landed-price constraints, compare AI-negotiated offers, join pools, approve final purchases, track deliveries and view receipts. PayPal Login authenticates a person; it does not grant a PayPool role or authorize payment.

Roles: RETAILER, SELLER, DRIVER, ADMIN. Users may have multiple roles, but active role/context must be explicit.

## Required stack
- Next.js App Router
- TypeScript
- Tailwind CSS
- TanStack Query
- React Hook Form + Zod
- Shared API types from packages/contracts or generated OpenAPI

Preserve existing versions and conventions. Do not upgrade major dependencies without approval.

## PayPal Login
Implement frontend entry into the backend-owned OAuth 2.0/OIDC flow. Browser must never receive PayPal client secret. Show Log in with PayPal; start backend authorization; handle callback through backend; fetch GET /api/v1/me and GET /api/v1/me/roles; show onboarding/pending approval when no active role; allow switching only among backend-granted roles; support logout and expired sessions. Never trust role names from query parameters, local storage, profile claims or user-editable frontend state.

## RBAC UI
- Protect retailer routes from unauthenticated users.
- Hide navigation items not allowed for current role.
- UI guards are UX only; backend authorization remains authoritative.
- Handle 401, 403 and expired sessions.
- Never expose admin screens without ADMIN.
- Never allow cross-retailer order access by changing URL IDs.

## Retailer pages
1. Dashboard: active requests, offers, pools, orders, deliveries and recent activity.
2. Procurement copilot: natural-language input, structured intent preview, clarifying questions, editable product/quantity/date/target price/hard ceiling/substitution permission; submit only after confirmation.
3. Catalog/search: filters and product cards/table with seller, stock freshness, price, unit and delivery eligibility; label substitutes.
4. Offer comparison: seller, product, quantity, base price, estimated freight, landed unit cost, delivery window and expiry; explain ceiling failures; enable counter/accept only when backend permits.
5. Pool details: state, participant count without revealing other retailers, cutoff, freight estimate and capacity progress.
6. Final review: itemized price, estimated vs final, ceiling check and explicit approval. AI must not trigger payment.
7. Orders/tracking: order and dispatch states, delivery estimate and exceptions.
8. Smart Receipts: summary and receipt view/download.
9. Profile/settings: business information and delivery location.

## API contracts to consume
- GET /api/v1/me
- GET /api/v1/me/roles
- POST /api/v1/procurement/parse
- POST /api/v1/procurement/requests
- GET /api/v1/procurement/requests/{request_id}
- GET /api/v1/catalog/search
- GET /api/v1/offers
- POST /api/v1/offers/{offer_id}/accept
- POST /api/v1/offers/{offer_id}/counter
- GET /api/v1/pools and GET /api/v1/pools/{pool_id}
- POST /api/v1/orders/{order_id}/approve
- GET /api/v1/orders and GET /api/v1/orders/{order_id}/receipt

If an endpoint is not ready, create a typed client and isolated mock adapter for local UI only. Do not invent a competing backend schema; record missing contracts.

## UX and security
Responsive desktop-first portal. Provide loading, empty, error, stale-data and success states. Use accessible labels and keyboard navigation. Display currency codes; do not assume INR is a live PayPal-supported domestic currency. Estimated freight must never look final. No secrets or payment tokens in client code/local storage. Prefer secure HttpOnly cookies. Sanitize user text; do not render untrusted agent output as HTML. Do not implement payment capture or payout.

## Acceptance criteria
- PayPal Login sandbox flow works through backend-owned OAuth/OIDC.
- Users without roles see safe onboarding.
- Multi-role users switch only among backend-granted roles.
- Retailer routes are role-protected.
- Retailer can enter natural-language request, review/edit extracted constraints and submit.
- Retailer can review offers, pool estimate, final price and explicit approval.
- UI shows backend-confirmed payment state, not redirect-derived state.
- No duplicate seller/driver/admin/payment backend logic.
- Tests cover auth states, role routing, validation and errors.
- Lint, typecheck and tests pass.

## Collaboration
Do not modify Member 2 or Member 3 module implementation files or their migrations. Shared contract changes go through docs/integration-contract-changes.md. Keep frontend in apps/web and identity in the agreed identity module. Commit small changes. At completion report files, routes, API dependencies, environment variable names only, tests, gaps and run commands.

## Execution
Inspect repository first and preserve existing code. Plan briefly, then implement incrementally. Do not rewrite unrelated files or use fake production credentials. Do not claim PayPal Login is configured until callback, redirect URLs and PayPal developer app settings are tested.