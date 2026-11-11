# PayPool product solution

PayPool gives independent retailers shared wholesale buying power without giving up control of their money or specifications. Regional distributors provide the inventory, commercial policy and delivery fleet. Compatible demand becomes an executable agreement only when product requirements, dates, stock, capacity, freight and every buyer's delivered-price ceiling pass deterministic checks.

The combined product definition and rationale are in [product decisions](product-decisions.md). This document replaces the earlier broad sponsor-oriented blueprint as the executable product summary.

## Journey

1. Retailer signs in and confirms a business delivery location.
2. The buyer describes a need or chooses a catalog SKU, quantity interval, date, hard ceiling and explicitly permitted alternatives.
3. Buyer/supplier policy agents compare serviceable inventory, earned tiers and demand. Gemini can assist interpretation and explanation when configured.
4. The buyer and supplier exchange versioned commercial proposals. Seller floors, buyer limits and specifications are validated; neither party can accept its own proposal.
5. Demand joins the distributor's zone/date run before cutoff. Optional recurring instructions create requests, not purchases.
6. Clearing locks demand, searches permitted whole quantities, validates stock/capacity/route minimums, apportions freight exactly and stores immutable agreement snapshots.
7. Each buyer reviews and approves its exact quote, then individually authorizes through PayPal sandbox or the explicitly labelled local simulator.
8. The supplier assigns an available vehicle and driver. Dispatch commits physical stock; the driver follows an ordered manifest and records append-only evidence or an exception.
9. Required buyer receipt confirmation permits capture. Provider responses and verified events produce a matched, pending or review-required receipt.
10. A dropout, expired quote or failed payment leads to void/reconciliation and a new agreement, or clean cancellation. Delivery exceptions lead to documented redelivery, void/close or merchant refund.

## Promise

No allocation clears above the buyer's hard ceiling. AI cannot change that ceiling, invent stock, silently substitute a product, approve a purchase or move money. Failed and uncertain operations remain visible and recoverable.

## Integration scope

The runnable application includes the portal, durable SQL domain, workers, payment adapters, private feed preparation and a pinned ACP continuation interface. The existing PayPal adapter needs merchant credentials and real sandbox verification. Native delegated payments, Vault and multi-merchant onboarding are not implemented; they require additional code and eligible partner access. Feed distribution is not activated. See the [acceptance audit](acceptance-audit.md) for the original requirements and remaining work.
