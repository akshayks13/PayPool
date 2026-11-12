# PayPool demo walkthrough

Use separate browser contexts for three retailers, distributor and driver. Start with a fresh temporary `DATABASE_URL` for repeatable figures. Prices are fictional USD fixtures and payments are simulated unless sandbox credentials are enabled.

After `make setup`, stop an existing run and use **`make demo`** for a fresh,
separate database on the normal localhost ports. This preserves the existing
development database, forces labelled simulated payments, and retains the new
database after stopping. Gemini follows the private local configuration; without
a key, the copilot is explicitly offline. Do not call the offline parser live AI.

### Included walkthrough data

Every `make demo` now seeds four scenes through the actual domain and simulated
payment services. Dates are relative to setup in Asia/Kolkata:

1. **Tomorrow:** all three 30 kg Harvest rice requests, ready to clear.
2. **+2 days:** cleared $48 allocations with three buyer authorizations, ready to recover by excluding buyer-c.
3. **+3 days:** dispatched route; Rahul and Meera delivered, Ananya awaiting driver evidence.
4. **+4 days:** all deliveries recorded and all buyers' receipts matched.

Use the dates printed at startup to select the correct card. AI comparison can
be shown without submitting another request: Ananya is already included in the
first run. Once a run is cleared, additional requests create another run rather
than changing the approved group. To show request creation from scratch, use a
different date and create all three buyers' requests before clearing.

The scenario seed refuses a database containing purchases and never calls real
PayPal. An already prepared database is left unchanged, including actions taken
during a rehearsal. Restart that database with `make dev`; another `make demo`
creates a new recording database. Normal `make dev` uses only the base seed.

## Story

Ananya needs 30 kg of Sona Masoori rice. The small-order price is $1.80/kg, before $7 delivery. Her ceiling is $1.70/kg delivered. Alone she cannot meet that limit or the distributor's 50 kg dispatch minimum.

Rahul and Meera each need another 30 kg on the same date. Their combined 90 kg earns the supplier's $1.50/kg tier. Shared freight is $9, divided equally across the equal shipments. Each quote is $45 goods + $3 delivery = **$48**, or **$1.60/kg delivered**. Each buyer approves and pays individually.

Meera then withdraws before dispatch. PayPool releases the old commitments and calculates the remaining 60 kg run. Freight becomes $8, split $4 each. Revised quotes are **$49** per shop. Ananya and Rahul must approve again. With a $1.60 ceiling the revised plan fails instead of charging more.

## Successful order

1. Use the already prepared three-request run for tomorrow. For a manual walkthrough in another run, each retailer selects **Sona Masoori rice** (Harvest) in Catalog: quantity 30–30, ceiling 1.70, same future date. Do not choose substitutes for this price walkthrough.
2. Distributor opens Delivery pools and **Optimize & lock final quote**. Show the freight breakdown and agreement version.
3. Each retailer approves their allocation, continues to payment, creates simulated checkout and simulates authorization. Sandbox mode requires real PayPal buyer approval.
4. Distributor sees 3/3 authorizations, assigns Kiran and dispatches.
5. Driver opens Today's route, sees ordered stops/navigation, and records 30 units, recipient name and acknowledgement with no exception at each stop.
6. Retailers open Receipts. A matched receipt requires both complete evidence and completed capture.

The seeded South zone intentionally permits simulated capture after acknowledged
driver evidence. A newly created zone defaults to authenticated buyer receipt
confirmation; in that case the buyer must confirm received goods before capture.
Driver acknowledgement alone is not independent buyer verification.

## Recovery

Use a second date/run and stop before dispatch. After authorization, distributor opens **Recover a changed order**, excludes Meera's request and recalculates. Show cancelled old agreement, voided authorizations, $49 replacement quotes and renewed consent. Repeat at a $1.60 ceiling to show an infeasible replacement.

## AI segment

Buying helper input: `30 kg Sona Masoori rice by YYYY-MM-DD, landed price below USD 1.70/kg.` Use a future date. Show supplier comparison, current demand and confirmation. Without a Gemini key the UI explicitly reports offline interpretation. Enable the model before calling this a live AI demonstration.

Show actual PayPal approval/capture references once credentials are configured. Describe constrained buyer/supplier coordination, bounded optimization and individually authorized merchant purchases. Avoid claims of production escrow, partner onboarding or live-road globally optimal routing.
