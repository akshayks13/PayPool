# Contracts

The current HTTP contract is generated from FastAPI's `/openapi.json`; interactive documentation is at `/docs` on the API server. Runtime request DTOs live in `backend/app/platform/models.py`, and the portal response types live in `frontend/src/lib/commerce.ts`.

- Login establishes an HttpOnly session cookie. `/api/v1/me` returns the session CSRF token; authenticated mutations require `X-CSRF-Token` and an allowed Origin when one is sent.
- Monetary fields ending in `_minor` are integer cents in the declared currency. `ceiling_minor` is per catalog selling unit; `total_minor` includes allocated freight.
- Final agreement approval requires the current pool version. Agreement hashes bind final allocations and product specification snapshots.
- Refunds require an `Idempotency-Key` bound to the same order, amount and reason. Provider events use provider event IDs for deduplication.
- Error responses use FastAPI's `detail` field. A provider-uncertain payment is persisted as `REQUIRES_RECONCILIATION`, not treated as success.

The `events` and `domain` directories are planning placeholders. No distributed outbox/event contract is claimed in this synchronous MVP.
