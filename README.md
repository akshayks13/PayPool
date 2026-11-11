# PayPool

PayPool is a B2B procurement platform that connects independent retailers and
regional distributors. The product blueprint and system decisions live in
[`docs/`](docs/).

## Repository layout

```text
frontend/       Next.js portal boundary (retailer, seller, driver, admin)
backend/        FastAPI modular-monolith boundary and workers
contracts/      Versioned API, event, and shared-domain contracts
infra/          Local development and deployment infrastructure
docs/           Product, architecture, module, and implementation notes
```

The current implementation includes a FastAPI negotiation foundation and a
Next.js portal preview. Local credentials, build output, virtual environments,
and installed dependencies are excluded from version control. See
[`docs/implementation.md`](docs/implementation.md) for completed work and
remaining features.

commands to run:
backend: python -m uvicorn app.main:app --reload  (or)  fastapi dev app/main.py

frontend: npm run dev