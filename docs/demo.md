# PayPool demo walkthrough

Use separate browser contexts for three retailers, distributor and driver. Start with a fresh temporary `DATABASE_URL` for repeatable figures. Prices are fictional USD fixtures and payments are simulated unless sandbox credentials are enabled.

## Story

Ananya needs 30 kg of Sona Masoori rice. The small-order price is $1.80/kg, before $7 delivery. Her ceiling is $1.70/kg delivered. Alone she cannot meet that limit or the distributor's 50 kg dispatch minimum.

Rahul and Meera each need another 30 kg on the same date. Their combined 90 kg earns the supplier's $1.50/kg tier. Shared freight is $9, divided equally across the equal shipments. Each quote is $45 goods + $3 delivery = **$48**, or **$1.60/kg delivered**. Each buyer approves and pays individually.

Meera then withdraws before dispatch. PayPool releases the old commitments and calculates the remaining 60 kg run. Freight becomes $8, split $4 each. Revised quotes are **$49** per shop. Ananya and Rahul must approve again. With a $1.60 ceiling the revised plan fails instead of charging more.

## Successful order

1. Each retailer selects **Sona Masoori rice** (Harvest) in Catalog: quantity 30–30, ceiling 1.70, same future date. Do not choose substitutes for this price walkthrough.
2. Distributor opens Delivery pools and **Optimize & lock final quote**. Show the freight breakdown and agreement version.
3. Each retailer approves their allocation, continues to payment, creates simulated checkout and simulates authorization. Sandbox mode requires real PayPal buyer approval.
4. Distributor sees 3/3 authorizations, assigns Kiran and dispatches.
5. Driver opens Today's route, sees ordered stops/navigation, and records 30 units, recipient name and acknowledgement with no exception at each stop.
6. Retailers open Receipts. A matched receipt requires both complete evidence and completed capture.

## Recovery

Use a second date/run and stop before dispatch. After authorization, distributor opens **Recover a changed order**, excludes Meera's request and recalculates. Show cancelled old agreement, voided authorizations, $49 replacement quotes and renewed consent. Repeat at a $1.60 ceiling to show an infeasible replacement.

## AI segment

Buying helper input: `30 kg Sona Masoori rice by YYYY-MM-DD, landed price below USD 1.70/kg.` Use a future date. Show supplier comparison, current demand and confirmation. Without a Gemini key the UI explicitly reports offline interpretation. Enable the model before calling this a live AI demonstration.

Show actual PayPal approval/capture references once credentials are configured. Describe constrained buyer/supplier coordination, bounded optimization and individually authorized merchant purchases. Avoid claims of production escrow, partner onboarding or live-road globally optimal routing.
