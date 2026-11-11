# PayPool — Frontend Implementation Prompt

> Original specification, retained for traceability. Current delivery and open work: [STATUS.md](STATUS.md). This file is not a completion report.

**File:** `docs/prompt_frontend.md`  
**Audience:** Frontend coding agent / frontend team  
**Scope:** Complete web portal UI across all PayPool roles and product modules  
**Primary stack:** Next.js App Router, TypeScript, Tailwind CSS

---

## 1. Your mission

You are the lead frontend engineer for **PayPool**, an AI-assisted B2B geo-procurement platform that connects independent retailers with regional wholesale distributors.

Build a cohesive, production-quality, responsive web application that supports the complete PayPool workflow:

1. Users authenticate through PayPal Login.
2. PayPool resolves internal roles and permissions.
3. Retailers create procurement requests using natural language or catalog search.
4. Buyer and distributor agents negotiate structured offers.
5. Compatible demand is grouped into distributor-specific delivery pools.
6. The platform calculates freight and runs deterministic allocation/optimization.
7. Retailers inspect the final landed cost and explicitly approve an order.
8. Orders move through payment, dispatch, delivery and proof-of-delivery.
9. Users inspect Smart Receipts, notifications and relevant audit information.

The portal is the primary product. ACP is a separate external agent-commerce integration; do not confuse ACP with the portal's conversational shopping experience or implement ACP protocol endpoints in the browser.

Your task is to implement the **frontend for every role and every module that requires a user interface**, not only the retailer dashboard.

---

## 2. Product rules that the UI must never violate

These rules are non-negotiable:

- **Landed unit cost** = negotiated wholesale unit price + allocated freight per unit (plus any explicitly itemized applicable fees/taxes where the product contract defines them).
- A retailer's allocation may clear only when its landed unit cost is less than or equal to its hard ceiling, `C_max`.
- `C_max` is a hard business constraint. Never allow an AI response, UI control, optimistic update or client-side calculation to silently change it.
- The backend is authoritative for prices, inventory, serviceability, pool membership, optimization, payment status, role permissions and order state.
- The frontend may display calculations supplied by the backend and may show clearly labeled estimates, but it must not make authoritative pricing or clearing decisions.
- Estimated freight and estimated landed cost must be visually distinct from locked/final values.
- An AI recommendation is not an accepted offer, order approval or payment authorization.
- A retailer must explicitly review and approve the final order before checkout begins.
- PayPal Login proves identity only. It does not grant a PayPool role and does not approve a payment.
- A browser redirect is not proof of payment. Show payment success only from backend-confirmed state.
- A substitute product may not be purchased unless the retailer has explicitly permitted/approved it.
- Do not expose one retailer's private business information, address, orders or pool participation details to another retailer.
- Do not expose private retailer addresses or unrelated seller data to other sellers.
- Do not present an application-generated Smart Receipt as a PayPal-issued receipt.
- Do not promise live domestic INR PayPal collection for Indian customers. Use environment/provider/currency labels supplied by backend configuration.

If the backend rejects an operation, show the authoritative reason and preserve the user's entered data where safe.

---

## 3. Technology and implementation standards

Use the repository's existing framework, versions, folder conventions and linting configuration. Do not replace or upgrade major dependencies without approval.

Preferred frontend stack:

- Next.js App Router
- TypeScript with strict mode
- Tailwind CSS
- TanStack Query for server state, caching and invalidation
- React Hook Form + Zod for forms and client-side input validation
- Shared API types from the existing contracts package or generated OpenAPI types
- A consistent accessible component system (reuse the project's existing library if present)
- MapLibre GL or Leaflet only where interactive maps are needed and already supported by the project

Engineering requirements:

- Build reusable components and role-specific layouts.
- Keep server state separate from transient UI state.
- Centralize API access, authentication handling, error mapping and query keys.
- Avoid `any`; use typed API responses and discriminated unions for state.
- Use stable IDs, not array positions, for list keys and resource navigation.
- Use server components where appropriate; use client components only for interactivity.
- Do not put secrets, PayPal client secrets, raw payment tokens or privileged credentials in browser code.
- Do not store authentication tokens or payment credentials in localStorage/sessionStorage.
- Prefer secure HttpOnly, Secure, SameSite cookies managed by the backend.
- Do not render untrusted AI or seller text as raw HTML.
- Add tests for important interactions, permissions, error states and workflow transitions.

---

## 4. Application structure and role-aware navigation

Create a shared authenticated application shell with:

- Responsive sidebar or navigation drawer
- Top bar with current user/business, active role, notifications and account menu
- Explicit active-role switcher when the backend grants multiple roles
- Breadcrumbs and page titles
- Consistent loading, empty, error and offline/stale states
- Accessible dialogs, confirmation flows, tables, filters and toasts

Roles:

- `RETAILER`
- `SELLER`
- `DRIVER`
- `ADMIN`

A user may have more than one role. The UI must only allow switching between roles returned by the backend. Never infer a role from a URL, query parameter, PayPal profile, locally edited state or hidden navigation item.

Suggested navigation:

### Retailer
- Overview
- Shop / Procurement Copilot
- Catalog
- My Requests
- Offers
- Delivery Pools
- Orders & Tracking
- Smart Receipts
- Notifications
- Business Profile & Settings

### Seller
- Overview
- Catalog & Products
- Inventory
- Pricing Tiers
- Service Areas
- Delivery & Fleet Settings
- Demand Pools
- Allocations
- Dispatch & Manifests
- Orders
- Notifications
- Seller Profile & Settings

### Driver
- Today's Route
- Assigned Stops
- Stop Details
- Proof of Delivery
- Delivery Exceptions
- Completed Deliveries
- Profile

### Admin
- Operations Overview
- User & Role Management
- Seller Verification
- Orders & Pools
- Payment/Integration Health
- Exceptions & Support
- Audit Log
- Feature/Environment Status

Do not expose routes or data merely because a user can guess a URL. UI route guards improve UX; backend authorization remains mandatory.

---

## 5. Authentication, onboarding and RBAC screens

Implement:

- Public landing / sign-in screen with **Log in with PayPal** entry point.
- Login initiation through the backend-owned OAuth 2.0 / OpenID Connect flow.
- Callback/return handling according to backend contract.
- Session bootstrap using `GET /api/v1/me` and `GET /api/v1/me/roles`.
- First-time onboarding when the account has no active PayPool role.
- Pending approval state when role or seller verification is awaiting review.
- Explicit role selection/switching for users with multiple backend-granted roles.
- Logout and expired-session handling.
- 401, 403 and 5xx error states.

The browser must never implement the OAuth token exchange using a client secret. Never trust role claims in query parameters or profile data. The backend validates identity and resolves internal membership.

---

## 6. Retailer frontend modules

### 6.1 Retailer dashboard

Show a useful summary of:

- Active procurement requests
- Offers requiring review
- Pools the retailer has joined
- Orders in progress
- Upcoming deliveries
- Recent notifications/activity

Each card must link to its corresponding detail page. Include first-use empty states with clear next actions.

### 6.2 Procurement copilot

Build a conversational procurement interface with:

- Natural-language request input
- Example prompts and optional guided entry
- Conversation history for the current procurement task
- Loading and agent-processing indicators
- Clarifying questions when required fields are missing
- Structured intent preview before submission

The structured preview should support fields returned by the backend, such as:

- Product and specification
- Quantity and allowed quantity range
- Unit/pack
- Desired delivery date/window
- Delivery location
- Target price
- Hard landed-price ceiling (`C_max`)
- Allowed substitutions and restrictions

Let the retailer edit extracted fields and confirm them before creating a request. Make it clear which values were extracted by AI and which were confirmed/edited by the retailer. Do not invent missing values.

### 6.3 Catalog and product discovery

Provide:

- Search box with keyword search
- Relevant filters (category, brand, specification, unit, availability, delivery date, seller where permitted)
- Product cards or table with image, name, variant, pack, unit, seller, stock freshness, price and serviceability
- Clear loading, no-results and stale-inventory states
- Product detail view

For substitute candidates:

- Label them as substitutes, not exact matches.
- Show relevant attribute differences and backend-provided match explanation.
- Clearly display whether substitution is permitted, pending approval or approved.
- Require explicit retailer consent where required.
- Never silently replace the requested product.

### 6.4 Procurement request details

Show:

- Request status and timeline
- Confirmed request constraints
- Product and quantity details
- Delivery date/location summary (mask sensitive details when not needed)
- Offers and negotiation progress
- Pool association when available
- Any validation issue or reason the request cannot proceed

Allow edits or cancellation only when the backend says the request is in an editable state.

### 6.5 Offer comparison and negotiation

Show structured offers and counters with:

- Seller/distributor
- Product/SKU and substitution status
- Offered quantity or range
- Negotiated wholesale unit price
- Estimated freight and estimated landed unit cost
- Delivery window
- Offer expiry
- Offer version and current state

Provide compare/sort/filter functionality. Show why an offer fails a ceiling or other constraint using backend validation results. Enable counter, accept or reject only when allowed by the backend state and permissions. Acceptance of an offer must not be presented as payment approval unless the API contract explicitly defines that operation.

### 6.6 Pool progress

Show the retailer's own pool status:

- Pool state and cutoff
- Aggregate progress/capacity indicator
- Retailer's own requested quantity
- Estimated freight share and estimate timestamp
- Estimated landed unit cost and ceiling status
- Next expected event/action

Do not reveal other retailers' identities, addresses, order contents or commercially sensitive details. Aggregate counts/quantities may be displayed only if the backend contract explicitly exposes them.

### 6.7 Final review and order approval

This is a critical confirmation screen. Before approval, show a clear itemized breakdown:

- Exact product/SKU and quantity
- Negotiated wholesale unit price and subtotal
- Locked/allocated freight
- Applicable fees/taxes, if returned by backend
- Final total and currency
- Final landed unit cost
- Retailer's `C_max`
- Backend ceiling validation result
- Delivery window and seller
- Any approved substitute
- Changes since the earlier estimate

Distinguish estimates from final locked values. If the final offer changes materially, require the backend's renewed approval flow. Provide an explicit confirmation action; do not trigger it automatically from a chat response or agent recommendation.

### 6.8 Orders and tracking

Provide order list and order detail views with:

- Order identifier/date
- Product lines and quantities
- Seller
- Payment state supplied by backend
- Fulfillment/dispatch state
- Expected delivery window
- Timeline and tracking updates
- Delivery exceptions and support guidance

Use backend order state transitions. Do not infer status from timestamps or browser redirects.

### 6.9 Smart Receipts

Display application-generated receipts containing the fields available from backend:

- Buyer/seller and order identifiers
- Product lines and delivered quantities
- Base unit price
- Allocated freight
- Fees/taxes and total
- Currency
- Landed unit cost and ceiling check
- Safe/masked payment reference and payment state
- Delivery/POD reference and exceptions
- Explanation of estimate-to-final differences
- Receipt verification status (`MATCHED`, `PENDING`, `REVIEW_REQUIRED`)

Support print/download only through a safe backend-provided route or generated document. Label it as a PayPool Smart Receipt, not a PayPal-issued receipt.

### 6.10 Retailer profile and settings

Support business name/contact details, delivery address/map pin, preferred delivery information and notification preferences according to backend contracts. Confirm before discarding unsaved changes.

---

## 7. Seller frontend modules

### 7.1 Seller dashboard

Show:

- Catalog item count and inventory alerts
- Active pools and demand summaries
- Allocations awaiting review
- Upcoming dispatches
- Recent orders and operational exceptions
- Seller onboarding/verification status

### 7.2 Seller profile and onboarding

Build forms for business details, contact information, operating locations and required verification status. Show review/pending/rejected states and backend-provided next steps. Do not imply that PayPal identity alone verifies the seller.

### 7.3 Catalog and product management

Support:

- Product and variant list/search/filter
- Create/edit/archive product and variant
- SKU, title, brand, category, unit, pack size and specifications
- Images through approved upload endpoints
- Unit weight and packed volume
- Active/inactive status
- Stock quantity and last-updated timestamp

Use server validation and show field-level errors. Confirm destructive actions. Do not let sellers modify another seller's catalog by changing IDs.

### 7.4 Inventory management

Show current stock, reserved/available quantities where exposed, freshness and low-stock warnings. Support authorized stock updates with clear confirmation. Warn when stock changes affect active offers or pools, based on backend response.

### 7.5 Volume pricing

Provide a tier editor for minimum quantity/weight and corresponding unit price. Validate ranges and overlaps client-side for usability, then rely on backend validation. Show active/pending status and effective dates if supplied.

### 7.6 Service areas and delivery configuration

Provide map-based drawing/editing of delivery polygons only if supported by the backend. Include:

- Service-zone name and active status
- Delivery schedules and cutoff
- Delivery windows
- Base route fee and stop fee
- Minimum route weight/threshold
- Vehicle maximum weight and volume
- Zone validation feedback

Clearly communicate that the backend validates geometry and eligibility. Do not use browser-only geometry as proof of serviceability.

### 7.7 Seller demand pools and allocations

Show seller-owned pools, lifecycle state, dispatch date/window, aggregate demand, estimated weight/volume, capacity utilization, route threshold and allocation summaries. Provide pool detail and allocation views. Protect retailer privacy; show only information the seller is authorized to access for its own pool.

### 7.8 Dispatch and manifest management

Show cleared orders, route manifest, assigned driver/vehicle, ordered stops and dispatch readiness. Allow authorized dispatch actions only when backend state permits. Display incomplete prerequisites and validation errors.

### 7.9 Seller orders and operational exceptions

Show order status, payment status as backend-confirmed, fulfillment state, delivery exceptions and reconciliation indicators. Do not implement payment operations owned by the payment service.

---

## 8. Driver frontend modules

Build a mobile-first, touch-friendly driver experience.

### 8.1 Today's route

Show only the authenticated driver's assigned route(s), with:

- Route summary and status
- Assigned vehicle
- Stop count
- Ordered stops
- Delivery windows
- Minimal delivery instructions

### 8.2 Stop details

Show only information required for that stop: order reference, recipient/business details permitted by backend, delivery location/navigation link, items/quantities and delivery instructions.

### 8.3 Proof of delivery

Support the backend-defined POD methods, such as delivered quantities, recipient acknowledgement, QR/signature/photo reference and timestamp. Show upload progress and retry states. Do not claim POD was recorded until the backend confirms it.

### 8.4 Delivery exceptions

Provide structured exception capture for backend-supported values, including:

- `DAMAGED`
- `MISSING_ITEMS`
- `RECIPIENT_UNAVAILABLE`
- `REFUSED`
- `ADDRESS_ISSUE`
- `OTHER`

Allow notes and evidence attachment only if supported. Explain that an exception is not a completed delivery. POD/exception records may be append-only; do not present an edit action if the backend does not support it.

### 8.5 Connectivity and safety

Design for narrow screens, large tap targets and unreliable connectivity. If offline drafts are supported, clearly mark them as unsent and synchronize only through an explicit, safe retry mechanism. Never fabricate a successful delivery state while offline.

---

## 9. Admin frontend modules

Admin pages must be inaccessible to non-admin roles at both navigation and route level, with backend authorization still authoritative.

### 9.1 Operations overview

Show operational counts and health indicators returned by backend: active users, seller verification queue, active pools, orders, exceptions, payment/webhook health and integration status.

### 9.2 User and role management

Support authorized user lookup, role membership review/grant/revoke and account status actions where APIs permit. Require confirmation for privileged changes and display audit feedback. Never allow users to grant themselves roles.

### 9.3 Seller verification

Show pending seller applications, submitted information, verification status, review notes and authorized approve/reject actions. Do not invent verification criteria.

### 9.4 Pool/order operations

Provide admin-level search and detail for pools/orders, state timelines, failed operations and exception context. Any intervention must be an explicit backend-supported action with confirmation and audit trail.

### 9.5 Payment and integration health

Show provider/environment/currency configuration, webhook health and integration readiness. Never display secrets, raw tokens, PAN/CVV or other payment credentials. ACP/Agent Ready should be marked unavailable/disabled unless backend configuration confirms access and enablement.

### 9.6 Audit log

Provide searchable, paginated audit events with actor, action, target, timestamp and safe metadata. Do not expose hidden model chain-of-thought or sensitive credentials.

---

## 10. API integration contract

Use the backend's actual OpenAPI specification and shared contracts as the source of truth. The following routes are known from the current project plan; confirm exact request/response schemas before implementation:

### Identity
- `GET /api/v1/me`
- `GET /api/v1/me/roles`
- Backend-owned PayPal OAuth start/callback and logout routes (confirm exact paths)

### Procurement and catalog
- `POST /api/v1/procurement/parse`
- `POST /api/v1/procurement/requests`
- `GET /api/v1/procurement/requests/{request_id}`
- `GET /api/v1/catalog/search`

### Offers
- `GET /api/v1/offers`
- `POST /api/v1/offers/{offer_id}/accept`
- `POST /api/v1/offers/{offer_id}/counter`

### Pools and orders
- `GET /api/v1/pools`
- `GET /api/v1/pools/{pool_id}`
- `POST /api/v1/orders/{order_id}/approve`
- `GET /api/v1/orders`
- `GET /api/v1/orders/{order_id}`
- `GET /api/v1/orders/{order_id}/receipt`

Seller, driver and admin endpoints must be taken from the shared OpenAPI/contracts as they are finalized. Do not guess endpoint names or payload fields.

### API client requirements

- Create a centralized typed API client.
- Include credentials/cookies according to backend session design.
- Normalize API errors into a shared error shape without discarding backend validation detail.
- Handle 401 by refreshing session state or returning to sign-in safely.
- Handle 403 with a clear permission message.
- Use TanStack Query for caching, invalidation and optimistic updates only where safe.
- Invalidate affected queries after mutations.
- Use idempotency keys only according to backend contract.
- Never retry non-idempotent operations blindly.
- Never treat a successful HTTP redirect as payment confirmation.
- If an API is not ready, implement a typed mock adapter isolated to local development/demo mode. Label mock data clearly. Do not create a competing schema or silently ship mocks in production.

---

## 11. Shared UI components to build

Create a reusable component layer for:

- App shell, role navigation and role switcher
- Page header, breadcrumbs and responsive layout
- Status badge and state timeline
- Data table with pagination, sorting and filters
- Search/filter toolbar
- Empty, loading, skeleton, error and retry states
- Form field wrappers and validation messages
- Confirmation dialog
- Toast/notification system
- Price breakdown and landed-cost panel
- Ceiling compliance indicator
- Product card and substitute comparison
- Offer comparison panel
- Pool progress/capacity panel
- Order tracking timeline
- POD capture form
- Receipt viewer
- Map/location picker
- File upload state
- Permission-denied and onboarding states

Avoid duplicating components across roles. Keep business logic in typed hooks/services rather than embedding it in presentation components.

---

## 12. Design and interaction expectations

The application should feel like a trustworthy B2B operations product, not a generic chatbot.

- Clear information hierarchy and concise business language.
- Consistent spacing, typography, color and status semantics.
- Responsive desktop-first retailer/seller/admin screens; mobile-first driver screens.
- Accessible contrast, keyboard navigation, focus states and semantic labels.
- Tables should remain usable on smaller screens through responsive layouts or deliberate horizontal scrolling.
- Financial values must always show currency and unit (for example, per kg).
- Use precise labels: `Estimated`, `Locked`, `Pending approval`, `Confirmed`, `Failed`.
- Do not use color alone to communicate status.
- Confirm consequential actions such as approving an order, dispatching a route, rejecting a seller or changing roles.
- Preserve form data after recoverable errors.
- Show timestamps and freshness for inventory, offers and estimates when supplied by backend.
- Do not invent ratings, seller verification, stock freshness or delivery ETAs.

---

## 13. Security and privacy checklist

- Route and component guards are not substitutes for backend RBAC.
- Do not trust user IDs, role IDs, seller IDs, pool IDs or order IDs supplied by the browser.
- Do not reveal cross-tenant data in search results, tables, autocomplete or error messages.
- Do not place secrets or raw payment/delegated tokens in frontend bundles, logs, analytics or browser storage.
- Do not log sensitive addresses or personal data unnecessarily.
- Sanitize/escape user, seller and AI-generated content.
- Validate uploaded file type/size in the UI, while relying on backend validation.
- Do not expose internal stack traces to end users.
- Do not render hidden chain-of-thought; show only concise, structured decision explanations returned by backend.
- Do not provide UI controls for prohibited agent actions such as changing `C_max`, granting roles, capturing payment or bypassing seller approval.

---

## 14. Testing requirements

Add tests for:

### Authentication and permissions
- Unauthenticated user cannot access protected pages.
- User with no role sees onboarding/pending state.
- Multi-role user can switch only to granted roles.
- Retailer cannot open seller, driver or admin pages without permission.
- Changing an ID in the URL does not expose another tenant's data (also verify backend enforcement).

### Retailer workflow
- Copilot extraction is editable and requires confirmation.
- Missing required fields trigger clarification.
- Substitute is clearly identified and requires consent.
- Offer comparison displays estimate and expiry accurately.
- Final approval displays backend ceiling validation.
- No agent response triggers payment automatically.
- Payment state is sourced from backend, not redirect query parameters.
- Receipt displays verification status correctly.

### Seller workflow
- Seller can manage only its own catalog and settings.
- Invalid pricing tiers and zone inputs show backend errors.
- Pool and allocation views respect seller scope.
- Dispatch is unavailable until backend says the pool/order is ready.

### Driver workflow
- Driver sees only assigned routes/stops.
- POD success appears only after backend confirmation.
- Exception does not mark a stop delivered.
- Failed upload/retry does not create duplicate POD records.

### Admin workflow
- Non-admin cannot access admin routes.
- Privileged actions require confirmation.
- Audit events and status updates reflect backend response.

Also add component tests for shared status, price breakdown, forms and error states, plus an end-to-end happy path for each role where test infrastructure permits.

---

## 15. Implementation sequence

Build incrementally in this order:

1. Inspect the repository and existing UI. Reuse its design system, routing, conventions and dependency versions.
2. Read the backend OpenAPI spec and shared contracts. Record missing/ambiguous contracts; do not guess them.
3. Establish app shell, design tokens, API client, query client, session provider and role-aware routing.
4. Implement PayPal Login entry, session bootstrap, onboarding and RBAC states.
5. Implement retailer procurement, catalog, request, offer, pool and final approval journey.
6. Implement seller dashboard, catalog, inventory, pricing, service zones, pool and dispatch screens.
7. Implement mobile-first driver route, stop, POD and exception screens.
8. Implement admin operations, seller verification, role management and audit screens.
9. Implement order tracking, notifications and Smart Receipt views.
10. Add loading/empty/error states, accessibility, tests and responsive refinements.
11. Run lint, type-check, unit/component tests and production build. Fix all failures.
12. Provide a concise implementation report listing completed modules, routes, tests, known backend dependencies and remaining gaps.

Do not build every screen as a static mock. Connect each completed screen to real typed API contracts wherever available.

---

## 16. Definition of done

The frontend is ready for integration when:

- All four roles have a coherent, role-aware experience.
- Every frontend module described in this prompt is implemented or explicitly marked as blocked by a missing backend contract.
- Authentication and role switching use backend-authoritative session data.
- Retailer can complete the request → offers → pool → final review → explicit approval journey.
- Seller can manage catalog/inventory/pricing/zones and review pools/dispatch through authorized APIs.
- Driver can view assigned stops and submit POD/exceptions.
- Admin can access only authorized operational controls and audit views.
- All price, inventory, allocation, payment and order states are backend-authoritative.
- No hard ceiling, consent or approval guardrail can be bypassed through the UI.
- Loading, empty, validation, permission, error and success states are implemented.
- The application is responsive, keyboard accessible and type-safe.
- Lint, type-check, tests and production build pass.
- No secrets, raw payment credentials or untrusted HTML are exposed.

At completion, report:
1. Pages/routes implemented by role.
2. Shared components and API hooks created.
3. Backend endpoints/contracts consumed.
4. Mocked or blocked integrations, with reasons.
5. Tests and build commands executed with results.
6. Remaining risks or decisions required from the backend team.
