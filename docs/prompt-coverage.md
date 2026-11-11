# Prompt coverage and integration contracts

> For an explicit delivered/unverified/not-implemented breakdown, read [delivery status](STATUS.md). This table is not a claim of 100% literal prompt completion.

The prompts are ownership plans, not proof of implementation. This report identifies the running services and explicit deployment dependencies.

| Prompt | Completed application behavior | Account/service verification |
| --- | --- | --- |
| 1: Identity/retailer | Server sessions, role/owner checks, expiry handling, no-role onboarding, profile/location, saved cross-device copilot tasks and confirmation, catalog/filtering, sortable offer comparison, revision history/counters/rejection, pools/approval, orders, recurring requests, receipts and agent access | Actual PayPal Identity login needs configured credentials/return URL |
| 2: Supplier/logistics | Catalog facets/server pagination, create/update/archive, metadata, reviewed CSV/XLSX imports, version-checked stock movements, pricing floor/tiers, Leaflet boundary editing, schedules/cutoffs, alpha-weighted freight, lock/optimization, immutable snapshots, fleet, manifests, POD/redelivery/exception closure | PostgreSQL checked; PostGIS SQL adapter requires an actual extension check. Gemini embeddings passed separately; Elasticsearch indexing/retrieval still needs the service |
| 3: Agents/commerce | Typed buyer/supplier policies, structured persisted proposals and offer revisions, exact-quote acceptance, persistent payment operations, checkout/auth/capture/void/refund, verified webhook ingestion, out-of-order reads, durable queue/receipts, pinned ACP sessions and discovery-feed preparation | Real Gemini extraction/narration/embeddings and the browser discovery flow passed; actual PayPal calls still need sandbox access. Delegated Braintree payments, Vault and partner merchant onboarding remain disabled |
| Frontend | Four connected role workspaces, role navigation, error/loading/empty states, map, pricing and freight breakdowns, receipt confirmation, recurring plans, fleet/inventory, print/export, worker recovery and responsive driver flow | Map tiles use OpenStreetMap and require browser connectivity; coordinates remain editable offline |

## Canonical routes

The current FastAPI `/openapi.json` is authoritative. A checked-in snapshot is in `contracts/http/openapi.json`. Monetary values use integer minor units and every financial action is tied to a buyer-approved order.

| Planned contract | Canonical implementation |
| --- | --- |
| Final order approval | `POST /api/v1/pools/{id}/approve` with version; creates the buyer's immutable order |
| Portal checkout | `POST /api/v1/orders/{id}/checkout`, `/authorize`, `/capture`, `/refund`, `/reconcile` |
| Pool lifecycle | `/pools/{id}/lock`, `/optimize` (or `/clear`), `/cancel`, `/replan` |
| Commercial offers | `/offers`, `/offers/{id}`, `/counter`, `/accept`, `/reject` |
| Catalog | `/seller/products`, `/seller/products/{id}`, `/archive`, `/seller/inventory`, `/catalog/search` |
| Logistics | `/seller/zones`, `/seller/zones/{id}`, `/seller/vehicles`, `/dispatch/{id}/manifest`, `/driver/routes/today` |
| Delivery evidence | `/orders/{id}/pod`, `/confirm-delivery`, `/resolve-exception` |
| Recurrence | `/standing-orders`, `/standing-orders/{id}/state` |
| Saved buying tasks | `/procurement/conversation`, `/procurement/conversation/reset`; `/procurement/discover` accepts `conversation_version` for guarded saves |
| Audit history | `/audit` with tenant-scoped SQL search and offset/limit pagination |
| Background operations | `/admin/operations`, `/admin/worker/tick`, `/admin/jobs/{id}/retry` |
| Receipts | `/orders/{id}/receipt` and `/receipt.html` |
| External agents | `/me/agent-access`, `/acp/checkout_sessions` and its update/retrieve/complete/cancel operations |

## Deliberate implementation choices

- One buyer request per delivery run, up to six buyers and 30,000 candidate manifests. These limits are enforced, not hidden. Each request concerns one catalog SKU with explicitly permitted alternatives.
- Whole quantities are exhaustively searched within that budget. Larger flexible-quantity runs must narrow their interval or split into runs.
- SQLAlchemy stores versioned domain documents in a shared SQL table. Alembic establishes and preserves the schema. A normalized enterprise schema and large-scale performance certification are separate work.
- The standalone worker uses the transactional SQL outbox. Redis/Celery is an optional executor over the same durable queue, not another source of truth.
- Security updates moved FastAPI to 0.162, Starlette to 1.10 and pytest to 9.2; pip was patched too. Tested dependency constraints preserve the resolved versions. These updates address audit findings rather than changing the requested product scope.
- Forms use native browser constraints and authoritative Pydantic validation. The earlier unused React Hook Form/Zod dependencies were removed rather than retaining vulnerable unused packages.
- Buyer/supplier agents run in-process with restricted authority. There is no claim that an external autonomous-agent runtime has been deployed.
- PayPal login uses the confidential authorization-code exchange and authenticated userinfo. It does not claim to validate an ID token that it never consumes.
- Public product feeds use real merchant content and base catalog prices. They do not publish automatically or enable checkout merely by setting a feed flag.

## Evidence

Backend tests cover the original foundation and complete application paths, including concurrent stock reservation, network calls outside SQL locks, durable uncertain operations, timeout-preserved POD, failed replans after voids, offer revisions, recurrence, queue retries, expiry, refunds and scoped ACP access. Browser tests exercise purchasing, recovery, negotiations, fleet/stock, map schedules, buyer confirmation and admin jobs. Separate real-service checks exercise PostgreSQL fulfillment and Redis/Celery consumption.
