# PayPool hackathon submission

Prepared against the [official PayPal AI Hackathon rules](https://paypalaihackathon.devpost.com/rules), checked November 11, 2026. Deadline: November 12 at noon PST, equivalent to **November 13, 2026 at 1:30 am IST**. Judging ends December 15; the submitted build must remain accessible for evaluation through that period.

## Submission readiness

| Requirement | Evidence / remaining action |
| --- | --- |
| Meaningful PayPal developer integration using sandbox | Genuine JavaScript SDK popup checkout, Personal buyer login, approval and $49 authorization passed locally and hosted. Signature-verified webhook handling passed on the hosted backend. Capture after delivery and real-provider void/refund still need end-to-end verification; simulator coverage is separate. |
| Meaningful AI | Gemini 2.5 Flash authenticated, extracted a written quantity and hard price ceiling into a validated intent, and produced a fact-constrained explanation in real API calls. The full Chromium copilot flow also passed: two catalog offers, AI explanation and explicit buyer confirmation. The local backend is configured for Gemini. Keys are private, ignored by Git and absent from submission materials. |
| Working runnable build | Connected four-role app at https://paypool-ai.vercel.app. README documents demo accounts, signup, popup checkout, local `make sandbox` and the separate `make demo` simulator. |
| Public open-source repository | Repository transferred to [akshayks13/PayPool](https://github.com/akshayks13/PayPool). The local remote and submission materials use this URL. The repository includes the MIT license and README setup instructions. Public main and its payment documentation have been checked without authentication. |
| Text description and tools | Current project story is in `devpost-project-story.md`; its payment status reflects real sandbox verification. |
| Public YouTube video under three minutes | Video URL and uploaded footage are managed by the team in Devpost. Existing simulator footage remains simulator evidence; current popup verification is documented separately. |
| Functional access for judges | Hosted app is public at https://paypool-ai.vercel.app. Supply app demo credentials and Personal sandbox buyer credentials in the appropriate private testing field; never publish API secrets. |
| Final Devpost entry | The team reports the entry is submitted and is updating its attachments and description. External Devpost edits remain the team representative's responsibility. |

Extra sponsor tools, PayPal Login, native delegated agent payments, Vault and multi-merchant onboarding are not baseline requirements. Do not expand the final demo around unavailable integrations. A simulator-only payment demonstration does not establish that the real PayPal sandbox path works.

## Draft project description

**PayPool — Wholesale buying power. Individual payment control.**

Independent retailers often need less stock than a distributor's economical delivery minimum. Buying extra ties up cash; buying together creates a coordination problem. Product specifications, delivery dates, supplier stock, freight and individual budgets must all agree, and one withdrawal can invalidate the group's deal.

PayPool turns compatible demand into a versioned purchasing agreement. Retailers describe their requirements naturally, review extracted quantities and a hard delivered-price ceiling, and explicitly confirm a buying request. Buyer and supplier policy agents compare eligible inventory and configured commercial terms. Gemini interprets requests and explains backend-calculated options; deterministic services enforce stock, permitted products, capacity, earned price tiers and exact freight allocation.

Each buyer reviews their own immutable allocation and approves its exact price. PayPool implements separate PayPal sandbox authorization and fulfillment-linked capture workflows, plus void, refund and reconciliation. The hosted app and `make sandbox` use genuine PayPal Sandbox popup checkout. Real buyer approval and authorization passed in both environments, with a signed webhook verified on the hosted backend. Capture after delivery remains unverified end to end; `make demo` separately simulates financial operations for repeatable rehearsals. PayPool never collects everyone's funds into an organizer's wallet.

When someone withdraws, PayPool releases or reconciles old commitments and seeks a replacement agreement. Revised prices require fresh consent. Suppliers manage inventory, delivery areas and fleet; drivers record delivery evidence or exceptions; buyers confirm receipt where required. Smart Receipts expose matched, pending or review-required states instead of assuming success.

The initial audience is independent shops served by a regional distributor. The differentiator is coordinated buying with individual authority and recoverable agreements, demonstrated through a concrete three-shop order and dropout scenario. Demo businesses and USD prices are fictional fixtures, not measured commercial savings or customer validation.

## Tools used

- PayPal JavaScript SDK and REST APIs: popup checkout, server-side OAuth, Orders, authorization and financial recovery operations, webhook verification and reconciliation. Sandbox checkout/approval/authorization are verified locally and hosted; capture and real-provider void/refund remain separate verification work.
- Gemini 2.5 Flash through Google GenAI: real structured request extraction and explanation of validated supplier facts. It has no authority to approve a purchase or move money.
- OR-Tools: bounded allocation selection and geographic route ordering, independently validated against hard constraints.
- FastAPI, Pydantic, SQLAlchemy/Alembic, Next.js, React, TypeScript, Tailwind and TanStack Query: API, persistence and connected portal.
- Leaflet: editable delivery zones. SQL outbox worker: schedules and recovery. Vercel serves the frontend; Render hosts the Docker API and worker; Neon PostgreSQL persists hosted data. Both application hosts deploy from GitHub main.
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
| [Render](https://paypalaihackathon.devpost.com/details/render) | Deployed on a free Docker web service under PayPool / Production, supervising the API and SQL worker. Connected to GitHub main and persistent Neon PostgreSQL; application health and worker activity have been verified. |
| [Zapier](https://paypalaihackathon.devpost.com/details/zapier) | Not integrated. Internal SQL jobs/notifications support the current workflow without connecting unrelated external accounts. |

The PayPal AI Toolkit and MCP resources are optional developer/agent interfaces. They are not required to make the portal AI-assisted. PayPool keeps financial execution in the approved order/payment service; it does not give a general-purpose model unrestricted payment tools. The hosted app and `make sandbox` call real sandbox APIs; only `make demo` and the controlled regression fixtures simulate payment responses.

## Recording plan — 2 minutes 45 seconds

| Time | On-screen action and narration |
| --- | --- |
| 0:00–0:20 | Show a shop's 30 kg need and $1.70/kg delivered limit. Explain why a small order misses the distributor's dispatch threshold. |
| 0:20–0:50 | Enter a natural-language request with a written quantity. Show the live Gemini interpretation, structured fields and buyer confirmation. State that the model proposes while the backend enforces limits. |
| 0:50–1:20 | Show three confirmed 30 kg requests and supplier clearing. Explain the fixture: 90 kg earns $1.50/kg; $9 shared freight gives each shop a $48 quote, or $1.60/kg delivered. Show each buyer's exact approval. |
| 1:20–1:45 | For new footage, show genuine sandbox popup login, buyer approval and the resulting AUTHORIZED state without leaving My orders. Keep the test-payment label visible. Existing simulator footage must remain described as simulator evidence. |
| 1:45–2:10 | On a separate prepared run, withdraw one buyer. Show old holds released, revised $49 quotes and renewed consent. Show that the same replacement fails at a $1.60 ceiling. |
| 2:10–2:35 | Show driver evidence, required buyer confirmation and reconciliation. Explain that exceptions or uncertain payment outcomes stay visible. |
| 2:35–2:45 | End with the audience and value: wholesale buying power with individual budget and payment control. Point to the runnable repository and state the final verified integration scope. |

Use the [demo walkthrough](demo.md) for setup. Record real screens in English, keep the video below three minutes, upload it publicly to YouTube, and review the complete submission against what the video actually demonstrates. The current live popup has real sandbox verification; do not describe older simulator footage or receipts as real sandbox capture evidence. See [payment verification](payments.md).
