# Free hosted demo: Vercel + Render + Neon

The public demo URL is the Vercel frontend URL. The frontend proxies `/api/*` to
Render so login cookies remain on the frontend origin. Keep API keys and database
credentials in Render's secret environment variables.

## 1. Persistent PostgreSQL on Neon

Create a **Free** Neon project. Copy its PostgreSQL connection string, keeping
`sslmode=require` (and other supplied connection parameters). Store it privately
as Render's `DATABASE_URL`. Do not commit it or put it in frontend variables.
Choose a region near the Render service. PostGIS is disabled for this demo.

## 2. Frontend project on Vercel

Import `https://github.com/akshayks13/PayPool`, select the branch containing the
deployment changes, and set **Root Directory: `frontend`**. Framework: Next.js.
Use the existing install/build defaults. Create the project and note its stable
production URL, such as `https://your-project.vercel.app`.

The initial frontend can deploy before the API is ready. Complete step 3, then
set Vercel's server-side `API_BASE_URL` to the Render HTTPS origin and redeploy.
The API URL must have no trailing slash and no `/api` suffix.

## 3. API and worker on Render

Create a **Blueprint** from the repository's `render.yaml` on the selected branch.
Review that the only resource is a **Free web service**; no paid database, disk,
Redis or separate worker is requested. Alternatively create a Docker web service:

| Setting | Value |
| --- | --- |
| Repository | `https://github.com/akshayks13/PayPool` |
| Dockerfile | `backend/Dockerfile` |
| Docker build context | repository root (`.`) |
| Instance | Free |
| Docker command | `python -m app.platform.hosted` |
| Health check | `/health` |

Set the three private/manual values prompted by the Blueprint:

- `DATABASE_URL`: the Neon PostgreSQL connection string.
- `PAYPOOL_FRONTEND_URL`: the exact Vercel production HTTPS origin, without a trailing slash.
- `GEMINI_API_KEY`: your Gemini key; backend only.

The Blueprint sets secure cookies, disables PostGIS and legacy APIs, enables
Gemini and explicitly uses simulated payments. `PAYPOOL_PREPARE_DEMO=true` seeds
the four walkthroughs only into a fresh database. Subsequent starts preserve
the existing scenarios. A non-empty database without the scenario marker is
refused: disable this flag to keep using that database without injecting data.
For explicitly offline interpretation, set `PAYPOOL_LLM_PROVIDER=deterministic`.

The hosted command migrates the database, optionally prepares scenarios and
supervises both API and SQL worker. If either exits, the service exits for the
hosting platform to restart it. It listens on `0.0.0.0:$PORT`. This is a single
instance demo arrangement; a paid separate worker is a future scaling option.

## 4. Connect and verify

1. Wait for Render's deployment, then open `https://YOUR-API.onrender.com/health`.
2. In Vercel, set `API_BASE_URL=https://YOUR-API.onrender.com` for Production and redeploy.
3. Open the Vercel URL, sign in using a demo account and confirm catalog/pool data loads.
4. Confirm the AI helper reports Gemini when a model call succeeds.
5. Test individual approval, simulated authorization, driver evidence and receipts.
6. Refresh and sign in again to confirm persisted state. Check Render logs and admin worker health.
7. Open the Vercel URL in an incognito window. Disable Vercel deployment protection
   for this public demo if it asks judges to sign in to Vercel.

Put the working **Vercel URL** in Devpost, along with the demo credentials.
Preview deployment origins are intentionally not allowed by the API; use the
configured stable production URL. If it changes, update `PAYPOOL_FRONTEND_URL`.

## Free-tier behavior

- Render Free sleeps after idle periods. The first request can take about a minute.
  Allow the backend to wake, then reload the app if its initial API request fails.
- API and worker both pause while Render sleeps; expiry, notifications and recovery
  resume on wake. There is no always-on background-processing guarantee.
- PostgreSQL persists purchases and uploaded media across Render restarts. SQLite
  or local files would be lost on its ephemeral filesystem.
- Neon and Vercel also have free-tier usage limits. This setup does not bypass them.
- Approval deadlines are real: prepared quotes can expire. For later judging,
  create new requests for a future delivery date; old receipts remain inspectable.
  To prepare brand-new scenes, use a new empty demo database, not a destructive reset.

References: [Render Free](https://render.com/docs/free),
[Render Docker](https://render.com/docs/docker),
[Neon Free](https://neon.com/blog/neon-free-plan-1-gb-per-project),
[Vercel environment variables](https://vercel.com/docs/environment-variables).
