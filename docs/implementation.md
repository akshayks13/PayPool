# PayPool implementation status

This document records what is currently implemented in the repository. It is a
development snapshot, not a claim that the marketplace is production-ready.

## Run backend tests

From the repository root, use this single PowerShell command:

```powershell
cd E:\paypool\backend; python -m pytest -q
```

The current suite has 13 tests.

## Implemented foundation

- Clean separated `frontend/` and `backend/` application boundaries.
- FastAPI application with `GET /health` and local CORS support for
  `http://localhost:3000`.
- Minimal Python requirements and test configuration.
- Git ignore rules for local `.env` files, Python environments, and Node build
  artefacts.
- Next.js App Router, TypeScript, Tailwind, and TanStack Query frontend setup.

## Implemented local login UI

- Temporary local sign-in form accepts any username and password.
- User must choose one role before entering a workspace.
- Retailer and Seller/Wholesaler are the current UX focus.
- Local sign-in stores no password and is reset on page refresh.
- This is a UI-only placeholder for the future PayPal Login and backend RBAC
  integration.

## Implemented frontend

### Shared UI

- Blue-and-white responsive portal shell, sidebar, top bar, sign-out action,
  role-specific navigation, cards, tables, dialogs, and status indicators.
- Local mock data is explicitly labelled as demo data.
- Every role navigation item renders a usable demo screen rather than a blank
  page.

### Retailer UI

- Retailer home with clear next actions.
- GPT-style `Buy with PayPool` chat interface.
- Suggested prompts, conversation history, loading state, error state, and a
  simple extracted-request review card.
- Retailer confirmation step before a request proceeds to seller discovery.
- Product discovery cards with simple shop-friendly terms.
- Buyer/seller negotiation conversation UI with explicit action buttons.
- Shared delivery, buying-list, orders, and receipt demo views.
- A live raw offer API test panel remains available under Prices & offers for
  development verification.

### Seller / Wholesaler UI

- Seller home with an operational checklist.
- Product list with SKU, pack, price, stock, and state.
- Excel/CSV product-sheet selection and review flow.
- File selection, discovered-column preview, and product-review demo state.
- Seller-side buyer-request and offer approval conversation UI.
- Demo views for stock, pricing, delivery areas, vehicles, shared orders,
  dispatch, orders, messages, and business settings.

### Driver and admin UI

- Role-specific navigation and populated demo workspace pages are available.
- These are not yet the focus of the detailed user-flow implementation.

## Implemented API endpoints

### Procurement and offers

- `POST /api/v1/procurement/parse`
  - Extracts a structured procurement intent.
  - Returns product, quantity, date, hard price ceiling, substitution consent,
    protected attributes, and clarification questions.
- `POST /api/v1/offers`
  - Creates a versioned structured offer.
- `GET /api/v1/offers?request_id=...`
  - Lists offers for a procurement request.
- `GET /api/v1/offers/{offer_id}`
  - Retrieves an offer.
- `POST /api/v1/offers/{offer_id}/counter`
  - Creates a counter version.
- `POST /api/v1/offers/{offer_id}/accept`
  - Fails closed until an authoritative allocation quote exists.

### Gemini-backed demo negotiation

- `GET /api/v1/demo/profiles`
  - Returns two local fixtures: GreenMart Kirana (retailer) and Sree
    Distributors (seller).
- `POST /api/v1/demo/negotiations/run`
  - Gemini extracts the buyer's natural-language request at runtime.
  - Buyer agent finds a constrained mock catalog candidate.
  - Seller yield agent selects only an earned seller-approved volume tier.
  - The API creates a real in-memory offer through the offer service.
  - Both buyer and seller approval remain `PENDING`.

Gemini is used only for structured request extraction. It cannot change the
price ceiling, stock, seller policy, allocation, approval, payment, or roles.
Those controls remain deterministic backend logic.

## Gemini configuration

Use local, ignored environment variables in `backend/.env`:

```env
GEMINI_API_KEY=your_key
PAYPOOL_GEMINI_MODEL=gemini-3.8-flash
PAYPOOL_LLM_PROVIDER=gemini
```

`OPENAI_API_KEY` is still accepted temporarily as a migration fallback for the
Gemini key variable name. New setups should use `GEMINI_API_KEY`.

## Test coverage implemented

- Offer creation, price-ceiling validation, countering, and fail-closed
  acceptance.
- Deterministic procurement parsing and required clarification questions.
- Buyer catalog recommendation stays within the hard ceiling.
- Seller tier recommendation is advisory and requires seller approval.
- Gemini output normalization and missing-field handling.
- Safe failure when LLM configuration is missing.
- Demo buyer/seller profiles and successful fixture negotiation.
- Demo negotiation stops safely for missing constraints.

## Pending features

### Authentication and authorization

- PayPal Login/OIDC flow, callback, logout, session cookie, `GET /api/v1/me`,
  `GET /api/v1/me/roles`, and backend-enforced RBAC.
- Real multi-role switching based only on backend-granted memberships.

### Retailer journey

- Persisted procurement requests and confirmation endpoint.
- Authoritative catalog search, product details, substitutes, seller
  serviceability, and address-aware delivery eligibility.
- Real agent tool calls to catalog, inventory, price-tier, pool-quote, and
  allocation-preview services.
- Pool membership, cutoff, live progress, final review, order approval,
  checkout, order tracking, notifications, and Smart Receipts.

### Seller journey

- Real product, variant, inventory, price-tier, service-zone, fleet, route
  fee, allocation, manifest, dispatch, and seller onboarding APIs.
- Excel/CSV upload endpoint, Gemini-assisted column mapping, human review, and
  transactional database import.
- Product retrieval/indexing so retailer search can find seller products.

### Driver and admin journeys

- Driver routes, stop permissions, POD capture/upload, and delivery exception
  APIs.
- Admin user/role controls, seller verification, payment health, feature
  status, support operations, and audit log APIs.

### Commerce, fulfillment, and persistence

- PostgreSQL/PostGIS schema, SQLAlchemy models, Alembic migrations, Redis,
  Celery tasks, outbox events, and durable repositories.
- Pool clearing, freight allocation, OR-Tools optimization, inventory races,
  and authoritative allocation quote integration.
- PayPal Checkout/Orders adapter, webhook verification/deduplication,
  reconciliation, optional India provider, and ACP adapter.
- Receipt generation using authoritative order, payment, and POD evidence.

### Frontend hardening

- Connect current mock screens to finalized APIs.
- Form validation with React Hook Form/Zod throughout every workflow.
- Component, permission, error-state, and end-to-end tests.
- Production build, lint, accessibility review, responsive device QA, and
  secure PayPal session integration.
