# PayPool hackathon submission

Prepared against the [official PayPal AI Hackathon rules](https://paypalaihackathon.devpost.com/rules), checked November 11, 2026. Deadline: November 12 at noon PST, equivalent to **November 13, 2026 at 1:30 am IST**. Judging ends December 15; the submitted build must remain accessible for evaluation through that period.

## Submission readiness

| Requirement | Evidence / remaining action |
| --- | --- |
| Meaningful PayPal developer integration using sandbox | Orders, authorization, capture, void, refund, verification and reconciliation adapters are implemented. **Current running payments are simulated at the team's request. A real sandbox transaction has not been verified.** Do not describe the simulation as a completed PayPal transaction. |
| Meaningful AI | Gemini 2.5 Flash authenticated, extracted a written quantity and hard price ceiling into a validated intent, and produced a fact-constrained explanation in real API calls. The full Chromium copilot flow also passed: two catalog offers, AI explanation and explicit buyer confirmation. The local backend is configured for Gemini. Keys are private, ignored by Git and absent from submission materials. |
| Working runnable build | Connected four-role application; setup, demo accounts and run commands in README. Offline simulator and optional configured service paths are distinguished. |
| Public open-source repository | MIT license exists locally. Unauthenticated GitHub API requests for `SajeevSenthil/paypool` returned 404 during this audit; public access is **not verified**. The latest implementation is committed locally and has not been pushed. Publish the actual submitted revision to an accessible public repository and verify its license is detected. |
| Text description and tools | Draft below; reconcile wording with the final recorded build before submitting. |
| Public YouTube video under three minutes | Not supplied or uploaded. Record actual running behavior using the script below, then add the public video URL to Devpost. |
| Functional access for judges | Repository setup instructions can satisfy this; hosting is optional. Give judges a working route to any required configured services. Never commit API secrets. A localhost URL alone is not remote access. |
| Final Devpost entry | Not submitted by this agent. The team representative must complete required fields and submit before the deadline. |

Extra sponsor tools, PayPal Login, native delegated agent payments, Vault and multi-merchant onboarding are not baseline requirements. Do not expand the final demo around unavailable integrations. A simulator-only payment demonstration does not establish that the real PayPal sandbox path works.

## Draft project description

**PayPool — Wholesale buying power. Individual payment control.**

Independent retailers often need less stock than a distributor's economical delivery minimum. Buying extra ties up cash; buying together creates a coordination problem. Product specifications, delivery dates, supplier stock, freight and individual budgets must all agree, and one withdrawal can invalidate the group's deal.

PayPool turns compatible demand into a versioned purchasing agreement. Retailers describe their requirements naturally, review extracted quantities and a hard delivered-price ceiling, and explicitly confirm a buying request. Buyer and supplier policy agents compare eligible inventory and configured commercial terms. Gemini interprets requests and explains backend-calculated options; deterministic services enforce stock, permitted products, capacity, earned price tiers and exact freight allocation.

Each buyer reviews their own immutable allocation and approves its exact price. PayPool implements separate PayPal sandbox authorization and fulfillment-linked capture workflows, plus void, refund and reconciliation. In the currently configured local build these financial operations use a clearly labelled simulator; real sandbox verification is still pending. PayPool never collects everyone's funds into an organizer's wallet.

When someone withdraws, PayPool releases or reconciles old commitments and seeks a replacement agreement. Revised prices require fresh consent. Suppliers manage inventory, delivery areas and fleet; drivers record delivery evidence or exceptions; buyers confirm receipt where required. Smart Receipts expose matched, pending or review-required states instead of assuming success.

The initial audience is independent shops served by a regional distributor. The differentiator is coordinated buying with individual authority and recoverable agreements, demonstrated through a concrete three-shop order and dropout scenario. Demo businesses and USD prices are fictional fixtures, not measured commercial savings or customer validation.

## Tools used

- PayPal REST APIs: server-side OAuth, Orders and payment operations, webhook verification and reconciliation; simulator is the current configured financial path.
- Gemini 2.5 Flash through Google GenAI: real structured request extraction and explanation of validated supplier facts. It has no authority to approve a purchase or move money.
- OR-Tools: bounded allocation selection and geographic route ordering, independently validated against hard constraints.
- FastAPI, Pydantic, SQLAlchemy/Alembic, Next.js, React, TypeScript, Tailwind and TanStack Query: API, persistence and connected portal.
- Leaflet: editable delivery zones. SQL outbox worker: schedules and recovery; PostgreSQL and Redis/Celery paths have separate local service checks.
- Postman collection/Newman: a portable simulator walkthrough passed 32 requests and 43 assertions, including three-buyer agreement, individual approval/authorization, fulfillment and reconciliation. Run `make postman-demo`; the runner uses its own disposable local database.

Gemini's actual embedding adapter also passed with 768-dimensional output. Elasticsearch/PostGIS remain optional adapters, not verified service deployments. ACP is a disabled-by-default external checkout continuation interface; native delegated payment processing is not claimed.

## Sponsor resource decisions

The baseline rules require PayPal and AI, not a count of sponsor integrations. The resources below were reviewed for fit. This table describes our implementation decisions, not a claim of prize eligibility or completed integrations.

| Resource | PayPool decision |
| --- | --- |
| [AG Grid](https://paypalaihackathon.devpost.com/details/aggrid) | Not integrated. Current bounded comparisons use an accessible sortable table. The sponsor describes deeper AG Studio dashboard/agent use for its award; a superficial grid dependency would not establish that. |
| [APIMatic](https://paypalaihackathon.devpost.com/details/apimatic) | Context Plugin not used or claimed. PayPal adapters use direct REST contracts; the running API exports OpenAPI. |
| [Astropods](https://paypalaihackathon.devpost.com/details/astropods) | Not integrated. Buyer/supplier policies run inside the application; a hosted autonomous-agent runtime is not required for the current workflow. |
| [Bryntum](https://paypalaihackathon.devpost.com/details/bryntum) | Not integrated. Delivery schedules and fleet assignment are implemented directly. A timeline could help a future multi-route operations product. |
| [Channel3](https://paypalaihackathon.devpost.com/details/channel3) | Not integrated. PayPool clears against the distributor's authoritative wholesale catalog and stock; external retail listings cannot establish its commercial terms or inventory. |
| [Elastic](https://paypalaihackathon.devpost.com/details/elastic) | Optional lexical/vector retrieval adapter exists. Gemini embeddings were verified; actual Elastic indexing/search still needs the service. SQL revalidates eligibility, stock and prices. No deployed Elastic claim. |
| [KERNEL](https://paypalaihackathon.devpost.com/details/kernel) | Not integrated. Procurement/payment services have API contracts and buyer approval; cloud browser automation is unnecessary for this flow. Local Playwright verifies the portal. |
| [Postman](https://paypalaihackathon.devpost.com/details/postman) | Integrated into the verification workflow through the checked-in runnable collection and pinned Newman runner. No cloud workspace publication is claimed. |
| [Render](https://paypalaihackathon.devpost.com/details/render) | Not deployed. Runnable repository instructions satisfy the permitted access route; hosted operation needs an account and deployment verification. |
| [Zapier](https://paypalaihackathon.devpost.com/details/zapier) | Not integrated. Internal SQL jobs/notifications support the current workflow without connecting unrelated external accounts. |

The PayPal AI Toolkit and MCP resources are optional developer/agent interfaces. They are not required to make the portal AI-assisted. PayPool keeps financial execution in the approved order/payment service; it does not give a general-purpose model unrestricted payment tools. The API adapter remains mocked until sandbox access is available.

## Recording plan — 2 minutes 45 seconds

| Time | On-screen action and narration |
| --- | --- |
| 0:00–0:20 | Show a shop's 30 kg need and $1.70/kg delivered limit. Explain why a small order misses the distributor's dispatch threshold. |
| 0:20–0:50 | Enter a natural-language request with a written quantity. Show the live Gemini interpretation, structured fields and buyer confirmation. State that the model proposes while the backend enforces limits. |
| 0:50–1:20 | Show three confirmed 30 kg requests and supplier clearing. Explain the fixture: 90 kg earns $1.50/kg; $9 shared freight gives each shop a $48 quote, or $1.60/kg delivered. Show each buyer's exact approval. |
| 1:20–1:45 | Show the configured payment path and its honest environment label. If sandbox has been verified, record actual buyer approval/authorization. Otherwise explicitly say this financial segment is simulated. Never edit a simulation label out of the footage. |
| 1:45–2:10 | On a separate prepared run, withdraw one buyer. Show old holds released, revised $49 quotes and renewed consent. Show that the same replacement fails at a $1.60 ceiling. |
| 2:10–2:35 | Show driver evidence, required buyer confirmation and reconciliation. Explain that exceptions or uncertain payment outcomes stay visible. |
| 2:35–2:45 | End with the audience and value: wholesale buying power with individual budget and payment control. Point to the runnable repository and state the final verified integration scope. |

Use the [demo walkthrough](demo.md) for setup. Record real screens in English, keep the video below three minutes, upload it publicly to YouTube, and review the complete submission against what the video actually demonstrates. The current simulated payment segment still needs real sandbox verification before claiming that integration is demonstrated.
