# Infrastructure status

The executable local composition is [`compose.yaml`](../compose.yaml), with the
API, portal, PostgreSQL/PostGIS, Redis and Celery worker/beat. Dockerfiles live in
`backend/` and `frontend/`. The current Compose file does not start Elasticsearch.

The default verified demonstration uses `make dev`: SQLite, the SQL outbox worker,
and localhost services. Container execution, PostGIS queries and Elastic retrieval
remain unverified in this environment; a valid Compose configuration alone is not
deployment evidence. Docker Desktop's daemon was stopped during the last check.

Nothing here claims an active Render deployment, production backup/restore,
autoscaling, managed monitoring or partner payment onboarding. See
[delivery status](../docs/STATUS.md) and the root README before deployment.
