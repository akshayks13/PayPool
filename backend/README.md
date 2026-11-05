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
