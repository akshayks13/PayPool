# Coding Agent Prompt 2 — Seller, Catalog, Geo-Pooling, Optimization and Fulfillment

You are Member 2 implementing seller operations and procurement clearing/logistics for PayPool.

## Ownership
You own seller profile/portal; catalog, variants, inventory and volume pricing; search indexing and substitute candidate retrieval; delivery-zone polygons and geospatial eligibility; pool lifecycle and allocation snapshots; freight and OR-Tools; manifests, driver assignment/UI, POD and exceptions; tests/migrations for these tables.

You do NOT own PayPal Login/RBAC, retailer portal, agent orchestration, ACP endpoints, PayPal payment/authorization/capture/payout/webhooks or receipt reconciliation. Consume identity/payment states through shared contracts.

## Product invariant
Each pool belongs to exactly one distributor in the MVP. For each included retailer/SKU: landed_unit_cost = negotiated_base_unit_price + allocated_freight / allocated_quantity. It must be <= retailer_C_max. Never relax the ceiling to make the solver return a solution.

## Required stack
Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL + PostGIS, Elasticsearch, OR-Tools CP-SAT or MIP, Pytest, and MapLibre GL or Leaflet for zone UI. Preserve existing versions.

## Seller portal
Implement seller profile/onboarding; product/variant CRUD; stock updates; title/brand/category/unit/pack/spec/weight/volume/images/active attributes; volume price tiers; delivery-zone drawing/editing; zone schedules, cutoff, delivery window, base route fee, stop fee, minimum route weight, max weight/volume; vehicle records; demand-pool dashboard with aggregate demand, estimated load, capacity utilization, allocations and expected revenue; manifest review and driver assignment. Tenant-scope all seller data.

## Catalog and search
Normalize catalog into canonical product/variant models. Validate units, quantities, currency, weight and volume. Keep stock timestamps. Index text and embeddings in Elasticsearch; hybrid search filters active seller, stock and serviceability. Return substitute candidates with similarity and attribute differences. Retailer consent is mandatory. Revalidate stock/price before pool lock. Wrap embeddings behind an adapter and provide deterministic keyword fallback for local tests.

## Geospatial serviceability
Use PostGIS SRID 4326 and GiST index. Example:
```sql
SELECT zone_id, distributor_id
FROM distributor_delivery_zones
WHERE is_active = TRUE
  AND ST_Contains(service_polygon,
      ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326));
```
Validate polygons and reject invalid geometry. Document boundary behavior: ST_Contains excludes boundary points; ST_Covers includes them. Never trust browser zone IDs without seller ownership checks. Do not expose retailer addresses to unrelated sellers.

## Pool lifecycle
Pool key: (distributor_id, zone_id, dispatch_date, delivery_window). States: DRAFT → ACCUMULATING → LOCKED → OPTIMIZING → CLEARED or FAILED → DISPATCHED → COMPLETED. Add eligible requests; prevent duplicate membership; update aggregate quantity/weight/volume; lock transactionally at cutoff; prevent join/cancel races; apply explicit minimum-route policy; store immutable versioned allocation snapshots; emit outbox events.

## Freight calculation
For retailer i: mu_i = alpha × (weight_i / vehicle_max_weight) + (1-alpha) × (volume_i / vehicle_max_volume). freight_i = total_route_freight × mu_i / sum(mu_j). total_route_freight = base_route_fee + sum(stop_fees). Alpha is configurable in [0,1]. Use Decimal or integer minor units; handle zero denominator; document deterministic rounding and residual allocation; return itemized freight; recalculate after membership, quantity, vehicle or route-fee changes; distinguish estimate from locked allocation.

## OR-Tools and validation
Enforce quantity lower/upper bounds, stock, max vehicle weight/volume, minimum route weight, zone eligibility, substitution consent and every retailer's C_max. LLM is never the constraint checker. Independently recalculate allocations, freight, landed costs and capacity after solver returns; reject invalid output. Cascade only through permitted quantity adjustments, approved substitutes, then bounded participant eviction/re-solve. Never alter C_max, minimum quantities, consent or stock to force feasibility.

## Manifest, driver and POD
Generate route manifest from cleared pool. A deterministic stop-order heuristic is acceptable for MVP but must not be called globally optimal. Assign driver/vehicle. Driver sees only assigned stops and minimum delivery data. POD includes stop/order IDs, delivered quantities, recipient acknowledgement, timestamp and optional QR/signature/photo reference. Exceptions: DAMAGED, MISSING_ITEMS, RECIPIENT_UNAVAILABLE, REFUSED, ADDRESS_ISSUE, OTHER. POD is append-only; corrections create follow-up event. Exceptions are not full delivery. Emit delivery.pod_confirmed or delivery.exception_reported; do not call PayPal APIs.

## APIs
- POST/PATCH/GET /api/v1/seller/products
- POST /api/v1/seller/inventory
- POST/PATCH /api/v1/seller/zones
- GET /api/v1/catalog/search
- GET /api/v1/geo/eligible-sellers
- POST /api/v1/pools; GET /api/v1/pools and /api/v1/pools/{pool_id}
- POST /api/v1/pools/{pool_id}/lock and /optimize
- GET /api/v1/pools/{pool_id}/allocations
- POST /api/v1/dispatch/{pool_id}/manifest
- GET /api/v1/driver/routes/today
- POST /api/v1/fulfillment/stops/{stop_id}/pod
- POST /api/v1/fulfillment/stops/{stop_id}/exception

Use shared identity context. If auth is not ready, use a clearly marked local test dependency, never a production bypass.

## Events
Publish catalog.product_updated, inventory.stock_changed, pool.created, pool.locked, pool.optimization_completed, pool.cleared, pool.failed, dispatch.manifest_created, delivery.pod_confirmed and delivery.exception_reported. Include event_id, event_type, occurred_at, correlation_id, aggregate_id, schema_version and payload. Use event bus/outbox; do not call Member 3 internals directly.

## Database ownership
seller_profiles, products, product_variants, inventory, price_tiers, distributor_delivery_zones, vehicles, delivery_schedules, delivery_run_pools, pool_members, pool_member_allocations, allocation_snapshots, dispatch_manifests, route_stops, proof_of_delivery and delivery_exceptions. Procurement requests only if agreed. Do not duplicate users, identities, payment, ACP or receipt tables.

## Acceptance criteria
Seller can manage catalog, stock, tiers, zones and vehicles. Search returns active/in-stock/serviceable products. Geometry tests cover boundary and invalid polygons. Pool has one distributor. Concurrent membership/lock safe. Freight sums to route freight within rounding tolerance. Solver output passes independent checks; no allocation exceeds C_max. Driver can submit POD/exceptions. Tenant isolation and API tests pass.

## Collaboration and execution
Do not edit Member 1 identity/retailer UI or Member 3 payment/ACP/agent/receipt logic. Publish API schemas/events early. Coordinate unique Alembic IDs. Inspect repo first, preserve working code, use seed fixtures only for local demos, and document heuristic limitations. At completion report modules, migrations, endpoints, events, tests, environment variable names, commands and gaps.