# Contracts

The current HTTP contract is generated from FastAPI's `/openapi.json`; interactive documentation is at `/docs` on the API server. Runtime request DTOs live in `backend/app/platform/models.py`, and the portal response types live in `frontend/src/lib/commerce.ts`.

- Login establishes an HttpOnly session cookie. `/api/v1/me` returns the session CSRF token; authenticated mutations require `X-CSRF-Token` and an allowed Origin when one is sent.
- Monetary fields ending in `_minor` are integer cents in the declared currency. `ceiling_minor` is per catalog selling unit; `total_minor` includes allocated freight.
- Final agreement approval requires the current pool version. Agreement hashes bind final allocations and product specification snapshots.
- Refunds require an `Idempotency-Key` bound to the same order, amount and reason. Provider events use provider event IDs for deduplication.
- Error responses use FastAPI's `detail` field. A provider-uncertain payment is persisted as `REQUIRES_RECONCILIATION`, not treated as success.

Domain events are persisted in the SQL outbox with `event_id`, `event_type`, `occurred_at`, `correlation_id`, `aggregate_id`, `schema_version` and safe `payload` metadata. Processing is at least once; projections deduplicate by event ID. The `domain` directory remains a planning namespace, while runtime DTOs live in the API package.

Pinned ACP schemas and the upstream license are under `contracts/acp`. Checkout sessions are bound to already approved internal quotes. Native delegated completion is disabled; see `docs/acp.md`.
