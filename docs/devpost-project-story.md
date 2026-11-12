# PayPool

**Tagline:** AI-powered group buying. Better prices. Your payment, your control.

## Project Story

### Inspiration

A small shop should not have to buy more than it needs just to qualify for a better price.

Independent businesses often face the same problem: their individual orders are too small to unlock wholesale pricing or economical delivery. Buying extra ties up cash and storage. Buying together sounds simple, until someone has to coordinate quantities, compare supplier terms, divide freight and collect everyone's money.

Then one participant drops out. The discount changes, delivery becomes more expensive, and the organizer has to start again.

That coordination problem inspired PayPool. We wanted to make collective purchasing practical while preserving something essential: **each business decides what it buys, what it spends and when it authorizes payment.**

### What it does

PayPool is an AI-assisted purchasing coordinator for independent retailers and small food businesses. It connects buyers, suppliers, drivers and operations staff through one purchasing workflow.

A buyer describes a need in natural language, including quantity, preferred price and maximum delivered cost. PayPool interprets the request and lets the buyer review the structured requirements before proceeding. Buyer and supplier policy agents help discover eligible offers and propose commercial alternatives. A deterministic clearing engine combines compatible demand and checks product rules, supplier minimums, price tiers, available stock, delivery capacity and shared freight.

Each buyer then sees an exact allocation and delivered price. Participation requires individual approval; a group's apparent saving never overrides someone's hard budget.

Consider an illustrative purchasing scenario: three shops each need 30 kg of a product. Their combined 90 kg earns a $1.50/kg supplier price. Sharing $9 of freight gives each shop a $48 order, or $1.60/kg delivered. PayPool checks that result against each buyer's approved requirements before asking them to commit.

The workflow connects those approved agreements to separate PayPal payment operations. Suppliers manage catalog, inventory and dispatch; assigned drivers record delivery evidence and exceptions; buyers can confirm receipt. Receipts and a reconciled ledger connect the commercial agreement to the resulting payment records.

### What makes PayPool different

The hardest part of group buying is keeping the agreement valid when circumstances change.

If a buyer withdraws or a payment fails, PayPool does not silently redistribute the cost. It releases or reconciles affected commitments, evaluates a revised arrangement and asks buyers to approve changed terms. If no arrangement satisfies their limits, the purchase cannot proceed under those terms.

PayPool coordinates demand rather than collecting everyone's money into an organizer's wallet. Its central principle is **collective buying power with individual financial authority.**

### How we built it

We built a connected Next.js and React frontend with TypeScript and Tailwind CSS, backed by a FastAPI application using Pydantic, SQLAlchemy and Alembic. Four role-based workspaces support retailers, suppliers, drivers and administrators.

Gemini interprets purchasing requests and explains validated supplier options. Buyer and supplier policy agents produce bounded recommendations, while deterministic services and OR-Tools handle allocation and routing constraints. The model cannot approve a purchase, override a budget or execute an unrestricted payment.

PayPool uses PayPal's JavaScript SDK to open checkout in a popup while the purchasing workspace stays visible. Each buyer signs in with a Personal sandbox account and approves their own exact purchase. The server creates and authorizes the order using PayPal REST APIs, checking the currency and total against the approved allocation. Payment operation intents are persisted before provider calls so uncertain results can be reconciled safely. Capture is linked to confirmed delivery; void, refund and webhook verification workflows support financial recovery.

The public app runs on Vercel, with the FastAPI backend and SQL worker on Render and persistent PostgreSQL storage on Neon. Both application deployments connect to the GitHub main branch. Transactional records, immutable agreement snapshots and a durable event outbox support scheduled work, notifications, receipts and recovery. We also built business profiles, supplier application reviews, catalog imports, product photos and authenticated delivery evidence so the purchasing journey extends beyond a checkout screen.

### Challenges we faced

**A discount is not the final price.** Product tiers and shared delivery costs depend on the actual group. We had to validate the complete allocation, distribute freight precisely and enforce each buyer's delivered-cost ceiling.

**A payment redirect is not proof of payment.** We separated buyer consent, provider authorization, fulfillment and reconciliation, recording each transition instead of treating them as one successful action.

**A changed group needs a new agreement.** Withdrawal and failure recovery required versioned terms, immutable snapshots and renewed consent, rather than editing an already approved order.

**AI needs clear boundaries.** Natural-language interpretation is useful, but financial correctness requires validated inputs, deterministic checks and explicit human approval.

### Accomplishments we are proud of

- Delivering a connected purchasing journey from natural-language requirements to negotiation, group clearing, individual approval, payment workflows, delivery and receipts.
- Handling a three-buyer purchase and participant withdrawal with revised terms, reconciled commitments and fresh consent.
- Bringing retailers, suppliers, drivers and administrators into role-based workspaces with onboarding, business profiles, catalog management and delivery evidence.
- Verifying critical domain rules and user journeys through backend tests, browser checks and a portable Postman walkthrough.
- Completing real PayPal Sandbox popup login, buyer approval and $49 authorization locally and on the hosted app, plus signature-verified webhook handling on the hosted backend.

**Payment validation:** the hosted app and `make sandbox` use genuine PayPal Sandbox, with no real money moving. Popup approval and authorization are verified; capture after delivery and the subsequent real-provider void/refund lifecycle remain to be verified end to end. `make demo` remains an explicitly labelled offline payment simulator for reproducible delivery and recovery walkthroughs.

### What we learned

The strongest use of AI in commerce is helping people reach a valid agreement while keeping authority explicit. A useful recommendation must survive stock checks, freight calculation, payment uncertainty and changes in participation.

We also learned that recovery is part of the product experience. Buyers need to understand what changed, what they have approved and what happens to their payment when a deal no longer works.

### What's next for PayPool

Our next step is to bring PayPool to existing buying clubs and regional distributors, helping more independent businesses turn shared demand into better purchasing opportunities. We plan to expand into more product categories and delivery regions, support larger purchasing groups and multiple suppliers, and introduce demand forecasting to help businesses coordinate recurring purchases. Through real-world pilots, we will measure savings, coordination time and delivery efficiency to guide that growth.

## Built with

Add these as individual Devpost tags:

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- SQLite
- PostgreSQL
- Next.js
- React
- TypeScript
- Tailwind CSS
- TanStack Query
- Google Gemini
- Google OR-Tools
- PayPal REST API
- PayPal JavaScript SDK
- Vercel
- Render
- Leaflet
- Pillow
- Pytest
- Playwright
- Postman
- Newman

## Project links

- [Live application](https://paypool-ai.vercel.app)
- [Public source repository](https://github.com/akshayks13/PayPool)
- [Payment flow and verification](https://github.com/akshayks13/PayPool/blob/main/docs/payments.md)
