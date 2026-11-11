# PayPool implementation status

This describes the running build. `solution.md`, `architecture.md`, prompts and contracts contain broader plans.

## Working flow

| Area | Implemented |
| --- | --- |
| Identity | Hashed passwords, persistent eight-hour sessions, HttpOnly cookies, CSRF/origin checks, lockout, server-granted roles and owner checks; optional PayPal sandbox code/userinfo login |
| Catalog | Persistent stock, earned volume tiers, protected variant attributes, keyword search, reviewed CSV/XLSX import with row errors and idempotent commit |
| Geography | Validated polygons, boundary-inclusive eligibility, depot and capacity configuration; optional indexed PostGIS `ST_Covers` and existing-zone backfill |
| Buying helper | Gemini structured extraction/narration when configured; explicitly offline deterministic mode; comparisons use persisted stock, tiers and demand |
| Buyer control | Confirmed quantities, snapshotted product specifications, approved substitutes, date and immutable ceiling; exact version/hash approval before checkout |
| Clearing | Bounded OR-Tools manifest search, reserved stock, route threshold, vehicle weight/volume, earned SKU prices, normalized footprint freight with exact-cent rounding, independent validation |
| Recovery | Void old uncaptured commitments, exclude withdrawn demand, calculate replacement, require new approvals; replay-safe replacement creation |
| Payments | Explicit simulator or genuine single-merchant PayPal sandbox AUTHORIZE, capture, void, refund and reconciliation adapters with stable operation IDs |
| Webhooks | Provider signature verification, event deduplication, trusted provider reads and capture-reference recovery |
| Fulfillment | Dispatch only after all included orders are authorized; assigned-driver route/navigation; append-only delivered quantities, acknowledgement and exceptions |
| Receipts | Downloadable JSON linking agreement, provider references and delivery evidence; pending/matched/review status; not a statutory tax invoice |
| Operations | Persisted account-scoped notifications/read receipts, audit, seller verification, role grants, location updates and environment status |
| Persistence | Serialized SQLAlchemy transactions over SQLite or PostgreSQL, durable sessions/agreements/payments/refunds/audit |

Live portal routes use the authenticated commerce API. Original preview components are retained as unmounted reference source. Identity-by-request fixture endpoints require both demo mode and the explicit legacy flag.

## Product decisions

PayPool's central strength is agreement formation and recovery:

1. Discovery estimates are distinct from executable quotes. AI cannot invent discounts, change protected specifications, approve purchases or move money.
2. Seller-configured tiers authorize prices. The running flow proposes earned alternatives; arbitrary autonomous seller negotiation is not claimed.
3. Each buyer pays the configured merchant. No organizer collects everyone else's money.
4. A dropout creates a new agreement and cost. Old authorizations are released and remaining buyers consent again.
5. Uncertain payment responses block dispatch, completed cancellation or further refunds until resolved. Delivery exceptions preserve evidence without pretending settlement succeeded.

## Bounds and remaining work

- At most six buyers and 30,000 manifests per pool; integer quantity candidates are request endpoints and tier breakpoints. Feasible interior quantities can be missed. This is not globally optimal continuous procurement.
- One request per buyer/run and one vehicle per pool. Routes use haversine distance; road-distance APIs, scheduling and live ETAs are future work.
- Persistence uses JSON domain snapshots in a generic SQL table. Normalized schema, managed migrations, archival, indexing and load testing remain production work.
- Provider calls execute synchronously within serialized transactions. Durable outbox, background workers, scheduled retries and operational recovery tooling remain; Redis/Celery are not running dependencies.
- Unknown provider outcomes without returned IDs can require manual provider investigation. The app fails closed rather than inventing payment references or blindly retrying refunds.
- POD records driver-submitted recipient evidence. Independent buyer OTP/signature, media uploads and fraud controls remain.
- Seller prices must include applicable tax. Provider fees, reverse logistics, partial-delivery settlement and returned-stock adjustments need explicit commercial policies.
- PayPal/Gemini credentials were not supplied. Adapters are implemented and mocked in tests; real sandbox purchases, signature-verified webhooks, Identity login and model calls must be checked with team credentials before submission. Optional PostGIS/Docker paths have not been exercised locally.
- ACP, delegated Braintree tokens, Vault, multi-merchant onboarding, live payments, Elastic vector search and distributed agent orchestration are outside this build. UI does not present them as connected.

## Validation

Current checks: **45 API tests**, **3 browser journeys**, TypeScript checks and production compilation. npm audit reports no known frontend vulnerabilities. Compose configuration validates; container execution was unavailable because the local Docker daemon is stopped.

`make test` runs API regressions and TypeScript checks. `npm run build` in `frontend` compiles production assets. `npm run test:e2e` exercises isolated browser journeys. Tests cover three-shop ordering, dropout repricing, infeasible revised ceilings, reserved stock, access isolation, payment uncertainty, refunds, receipts and restart persistence.
