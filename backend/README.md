# Backend boundary

The backend will use Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2,
PostgreSQL/PostGIS, Redis, and Celery. It is a modular monolith: modules own
their use cases and persistence models and expose services, contracts, and
events rather than direct table access.

Provider adapters belong in `app/integrations`; solver work belongs in
`modules/optimization`; background-task entry points belong in `app/workers`.
Keep migrations in a single coordinated Alembic history.

## LLM configuration

Procurement parsing uses the Gemini API with Pydantic structured outputs by
default. Set `GEMINI_API_KEY` and optionally `PAYPOOL_GEMINI_MODEL` (default:
`gemini-3.8-flash`) before calling
`POST /api/v1/procurement/parse`. Set `PAYPOOL_LLM_PROVIDER=deterministic`
only for offline local development and tests. The LLM extracts an intent; it
never approves orders or becomes the authority for price ceilings.

The same Gemini configuration is used by
`POST /api/v1/agents/negotiations/recommend` to write simple buyer/seller
messages from application-validated facts. It cannot call tools or change
terms. `PAYPOOL_LLM_TIMEOUT_MS` bounds each Gemini request (20 seconds by
default). Set `PAYPOOL_AGENT_NARRATOR_PROVIDER=deterministic` only for offline
development and automated tests.

Transient Gemini 5xx and network failures are retried with bounded exponential
backoff. `PAYPOOL_LLM_MAX_RETRIES` defaults to `2` and
`PAYPOOL_LLM_RETRY_BACKOFF_MS` defaults to `500`; authentication, quota, model,
and schema errors are not retried.
