# PayPool: combined product definition

PayPool coordinates pooled wholesale purchases for independent shops served by a regional distributor. It combines the B2B proposal's catalog, geography, pricing and delivery operations with PACT's agreement, consent and recovery rules.

## Problem statement

Independent retailers struggle to earn wholesale prices without overbuying, while distributors struggle to fill viable delivery runs. Combining orders helps only when product specifications, quantities, delivery dates, vehicle capacity, freight and each buyer's budget agree. PayPool's buyer and distributor agents interpret demand and propose bounded commercial terms; deterministic clearing verifies a shared order, and each retailer approves its own exact allocation and authorizes its own payment. A withdrawal, failed authorization or changed offer triggers regrouping, renewed approval or cancellation. Delivery evidence, buyer confirmation and provider reconciliation close the transaction without an organizer holding everyone else's money.

## What each source contributes

| Decision | PACT contribution | B2B contribution | PayPool implementation |
| --- | --- | --- | --- |
| Customer | Existing groups with real coordination friction | Independent shops and regional distributors | A concrete distributor-led buying group |
| Agreement | Explicit specifications, ceilings and renewed consent | Tier prices, zone, cutoff and vehicle limits | Versioned offers plus an immutable executable quote |
| AI | Interpret and compare compatible needs | Buyer and distributor policy agents | Typed in-process agents, optional Gemini interpretation/narration, persisted proposal runs |
| Failure | Regroup, renegotiate or cancel | Cascade clearing and delivery exceptions | Old holds released before replacement; failed replans remain auditable |
| Payments | Separate buyer authority and reconciliation | Authorize, fulfill and capture | Exact individually approved merchant payments; no pooled wallet |
| Operations | Organizer coordination | Inventory, fleet, route and POD | A working supplier/driver workflow and durable jobs |

## Corrections to the PDF

1. A ceiling below the standalone catalog price is valid: earning a shared discount is the point of pooling.
2. Embedding similarity never constitutes consent. Requested specifications and explicitly permitted SKUs remain authoritative.
3. Quantity and freight relationships are not casually labelled a linear model. The running solver searches whole quantities within an explicit manifest budget and validates the result independently.
4. Authorization is not escrow. Capturing directly for a configured merchant does not require an invented second payout.
5. Vaulting, delegated payments and partner multi-merchant products need real account eligibility. Their status is visible instead of simulated as a connected integration.
6. A driver-submitted acknowledgement is evidence, not independent buyer verification. Live capture requires the buyer's authenticated confirmation.

## What the demo should prove

Three shops can earn a viable shared offer. Each shop can inspect and approve its final delivered price. Losing one shop changes the quote and invalidates old consent. An infeasible replacement fails safely. A delivery exception preserves the evidence and money state. The system can recover after a provider timeout or worker restart.

This is the product's differentiator. A larger sponsor list is not evidence of a stronger system.
