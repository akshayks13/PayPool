# Repository structure and module boundaries

This repository uses a modular monolith for the MVP. `frontend` and `backend`
are independently deployable application boundaries; business capabilities are
kept cohesive inside each boundary. A module may depend on shared contracts,
but modules must not reach into one another's persistence models.

## Layout

```text
paypool/
├── frontend/                 # Next.js portal; no authoritative business rules
│   └── src/
│       ├── app/              # App Router route groups and layouts
│       ├── components/       # reusable UI components
│       ├── features/         # role and capability-oriented UI features
│       ├── lib/              # API client, auth/session helpers, formatting
│       └── types/            # generated/consumed contract types
├── backend/                  # FastAPI modular monolith and async workers
│   ├── app/
│   │   ├── core/             # config, security, logging, errors, feature flags
│   │   ├── modules/          # independently owned domain modules
│   │   ├── integrations/     # provider adapters only
│   │   └── workers/          # Celery task entry points and task routing
│   ├── migrations/           # Alembic revisions, one coordinated history
│   └── tests/                # unit, integration, contract, and property tests
├── contracts/                # API/event schemas before implementation
│   ├── http/                 # OpenAPI fragments and error conventions
│   ├── events/               # outbox event schemas
│   └── domain/               # shared DTOs and state-machine definitions
├── infra/                    # compose, local services, and deployment assets
└── docs/                     # decisions, workflows, and operational notes
```

## Backend module map

| Module | Owns | Primary collaborators |
|---|---|---|
| `identity` | users, external identities, memberships, sessions | PayPal Identity adapter |
| `retailers` | retailer profiles and delivery preferences | identity, procurement |
| `sellers` | seller profile, onboarding, commercial configuration | identity, catalog, geo |
| `catalog` | products, variants, inventory, price tiers, search documents | sellers, search adapter |
| `geo` | zones, schedules, vehicles, serviceability | sellers, pools |
| `procurement` | requests, request items, offers, revisions, consent | catalog, negotiation |
| `negotiation` | typed buyer/yield-agent orchestration and evidence | procurement, AI adapter |
| `pools` | pool lifecycle, membership, allocations, snapshots | geo, optimization |
| `optimization` | freight allocation, solver execution, invariant validation | pools, catalog |
| `acp` | ACP feed, checkout sessions, protocol events | catalog, orders, payments |
| `payments` | payment orders, captures, verified webhooks, reconciliation | provider adapters, orders |
| `fulfillment` | orders, manifests, stops, POD, exceptions | pools, payments |
| `receipts` | Smart Receipts, notifications, audit events | fulfillment, payments |

`orders` belongs to `fulfillment` for the MVP. It may become a separate module
only when its lifecycle requires independent ownership.

## Cross-cutting rules

- Backend code enforces RBAC, tenant ownership, idempotency, and all monetary
  and allocation invariants. The frontend only presents server results.
- The hard landed-price ceiling (`C_max`) is deterministic backend logic, never
  agent or frontend logic.
- Modules communicate through application services and versioned contracts;
  asynchronous changes are published through an outbox event.
- Provider-specific code stays in `backend/app/integrations`; provider types do
  not leak into module-domain models.
- Money is represented by integer minor units or `Decimal`; never floats.
- ACP remains isolated and feature-flagged until protocol and provider access
  are confirmed.

## Recommended delivery order

1. Add repository tooling, local Docker Compose, contracts, database base, and
   identity/RBAC foundations.
2. Implement seller/catalog and geo modules with retailer catalog discovery.
3. Add procurement, negotiation, pools, and deterministic optimization.
4. Add explicit approval, payments/webhooks, fulfillment, receipts, and audit.
5. Enable ACP only behind its feature flag after integration eligibility is
   confirmed.
