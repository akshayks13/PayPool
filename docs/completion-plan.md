# PayPool completion plan

> This checklist covers the delivered application scope. It does **not** mean every original prompt/PDF feature or live integration is complete. See the authoritative [delivery status](STATUS.md), including unfinished work.

Product: pooled wholesale procurement for independent shops, with PACT's explicit agreement, immutable limits, individually authorized payments, and recovery when terms change.

The PDF is the customer/workflow foundation. Corrections: no claim of escrow; no automatic substitute consent; a buyer may set a ceiling below the standalone price; solver guarantees apply to verified outputs, not an invented linear formulation; partner-only payment products remain disabled without access.

## Delivery checklist

- [x] Review prompts 1, 2, 3, frontend specification and the complete source PDF.
- [x] Preserve the tested core and rename the branch.
- [x] Durable versioned offers/counters with authenticated actors, expiries and final-quote validation.
- [x] Full catalog metadata, stock movements, filters and optional external search adapter.
- [x] Editable delivery polygons, schedules, cutoffs, configurable freight weights and fleet assignment.
- [x] Persistent lock/optimization lifecycle, immutable allocation snapshots and bounded integer quantities.
- [x] Recurring buying instructions that create requests but never authorize a purchase.
- [x] Transactional outbox, worker/scheduler, retry diagnostics and schema migrations.
- [x] Delivery confirmation and exception recovery; complete payment/receipt reconciliation.
- [x] Version-pinned ACP contract adapter, authenticated/idempotent endpoints and disabled payment completion without eligible provider access.
- [x] Coherent retailer, supplier, driver and admin screens backed by the actual services.
- [x] Updated OpenAPI, setup, product decisions and prompt coverage with tests/build evidence.
- [x] Saved cross-device buying task with stale-write protection and refreshed estimates on restoration.
- [x] Server catalog facets/pagination, commercial offer comparison/revision/rejection, and complete accessible audit pagination.
- [x] Simulator-only Postman walkthrough and disposable one-command runner; real Gemini embedding adapter check.

Actual PayPal, Identity and Gemini verification requires team credentials. Native delegated payments, external signed event delivery and partner merchant onboarding require additional implementation/access; credentials alone do not complete them. See [delivery status](STATUS.md).
