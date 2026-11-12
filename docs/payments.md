# PayPal checkout and payment verification

## Running modes

| Mode | Command or URL | Payment behavior | Storage |
| --- | --- | --- | --- |
| Local simulator | `make demo` | Explicitly simulated; never calls PayPal | New separate recording database |
| Local sandbox | `make sandbox` | Genuine PayPal Sandbox popup | `backend/data/paypal-sandbox.db` |
| Hosted sandbox | https://paypool-ai.vercel.app | Genuine PayPal Sandbox popup | Neon PostgreSQL |

Sandbox purchases use test money. PayPool's demo account is separate from the
Personal sandbox buyer used inside PayPal. Public app account credentials are
in the root README; buyer passwords and server secrets are not committed.

## Local setup

1. Install dependencies with `make setup`.
2. Add sandbox `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` privately to
   `backend/.env`, preserving existing Gemini configuration.
3. Stop the existing localhost app, then run `make sandbox`.
4. Open http://localhost:3000, select a retailer and approve a cleared quote.
5. Open **My orders**, click the PayPal button, sign in as a Personal sandbox
   buyer and approve. The popup closes and the order becomes **AUTHORIZED**.

The launcher starts frontend, API and SQL worker together, forces sandbox mode
and localhost return URLs, and preserves simulator/development data. Labelled
buying groups are prepared daily without inventing authorizations or receipts.
Existing browser sessions may need a fresh sign-in after changing databases.

The registered team webhook points to the hosted backend. Local authorization
works through the popup callback and server reconciliation. To receive signed
webhooks locally, configure a separate public HTTPS listener and webhook ID.

## Checkout sequence

1. Buyer approves the exact current quote and creates a PayPool order.
2. Frontend gets the public SDK client ID from `/api/v1/config`. The OAuth secret
   never reaches the browser. The SDK loads only for sandbox payment controls.
3. PayPal's `createOrder` callback calls `POST /api/v1/orders/{id}/checkout`.
   The server validates ownership, agreement, merchant and amount, persists a
   payment operation, and creates or reuses its PayPal order idempotently.
4. SDK opens PayPal checkout in a popup. The parent stays on **My orders**.
5. After buyer approval, `onApprove` calls `POST /api/v1/orders/{id}/authorize`.
   The server reads PayPal state and checks currency and total against the
   immutable buyer-approved amount before authorizing.
6. The app refreshes its order projection and displays **AUTHORIZED**. A browser
   callback or redirect alone is never proof of authorization.
7. Signed webhooks are verified against PayPal before reconciliation. Uncertain
   operations remain inspectable and block conflicting financial actions.

Both SDK and Orders API use authorization intent. Capture is deferred until
complete delivery evidence and authenticated buyer receipt confirmation satisfy
the sandbox payment rules. Authorization is not a captured payment.

## Recovery and fallback

- Closing the popup leaves the order retryable and does not mark it authorized.
- The button waits for SDK initialization. Slow loading displays a useful status
  and offers retry or **Having trouble opening PayPal? → Use full-page checkout**.
- The full-page fallback reuses the server checkout and returns to the configured
  frontend order page; it is an explicit fallback rather than the primary flow.
- SDK errors and server authorization failures never display a successful payment.
  Use the order's reconciliation control before retrying an uncertain operation.
- A changed or expired agreement requires valid terms and renewed buyer approval.
- The seeded distributor is the configured sandbox merchant; supplier application
  approval does not connect another merchant to PayPal automatically.

## Verification evidence

Real-provider checks completed on November 13, 2026:

| Check | Local sandbox | Hosted sandbox |
| --- | --- | --- |
| Genuine SDK button and popup | Passed | Passed |
| Personal buyer login and approval | Passed | Passed |
| $49 server authorization and app status update | Passed | Passed |
| Parent remains on My orders | Passed | Passed |
| Signature-verified webhook and persisted receipt evidence | No local HTTPS listener | Passed |
| Delivery-triggered capture, void and refund end to end | Not yet verified | Not yet verified |

Focused regression checks also cover cancellation/retry, SDK load failure with
fallback, authorization failure never appearing successful, public client ID
without OAuth secret exposure, and optional PayPal amount breakdown handling.

Run relevant automated checks after payment changes:

```sh
(cd backend && .venv/bin/python -m pytest -q tests/test_paypal_amounts.py)
(cd frontend && npm run typecheck)
(cd frontend && npm run test:e2e -- paypal-popup.spec.ts)
```

The browser regression test uses controlled SDK callbacks and mocked payment
responses to test application behavior; it does not spend sandbox funds. The
real-provider checks above were performed separately with actual sandbox orders.

## References

- [PayPal standard checkout callbacks and popup](https://developer.paypal.com/studio/checkout/standard/integrate)
- [PayPal JavaScript SDK v5 configuration](https://developer.paypal.com/sdk/js/v5/configuration)
- [Hosted deployment setup](deployment.md)
