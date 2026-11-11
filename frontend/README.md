# PayPool portal

The running Next.js portal connects retailer, supplier, driver and admin screens
to the FastAPI services. Authentication uses backend-owned sessions, server roles,
HttpOnly cookies and CSRF protection. Arbitrary passwords and client-selected
roles do not grant access.

Start the complete application from the repository root:

```sh
make setup
make dev
```

Open `http://localhost:3000/login`. Use the seeded demo account selector and the
development password documented in the [root README](../README.md). Separate
browser profiles let you demonstrate several roles concurrently. Demo credentials
are rejected when the backend runs with demo mode disabled.

For just the portal, after installing dependencies:

```sh
cd frontend
npm run dev -- --hostname localhost --port 3000
```

The API must also be running. `API_BASE_URL` is a server-only setting for the
same-origin `/api` proxy; it defaults to `http://127.0.0.1:8000`.

The route `app/[role]/[[...section]]/page.tsx` renders `PortalShell`, which uses
`CommerceWorkspace`, `ConnectedCopilot` and `PlatformFeatures`. Older standalone
prototype components are not routed and are not evidence of running features.
The active screens use persisted API state, including catalog, offers, pools,
approval, delivery, receipts and operations.

```sh
npm run typecheck
npm run build
npm run test:e2e
```

Browser tests launch isolated local API/portal processes with a fresh database.
Real Gemini checks are separate from the deterministic browser suite. PayPal
is currently simulated at the team's request; it is always labelled.

Read [delivery status](../docs/STATUS.md) for remaining work and
[prompt coverage](../docs/prompt-coverage.md) for canonical API contracts.
