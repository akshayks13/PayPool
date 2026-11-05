# PayPool portal

Next.js App Router portal for retailer, seller, driver, and admin experiences.

## Run locally

```powershell
cd frontend
npm.cmd install
Copy-Item .env.example .env.local
npm.cmd run dev
```

Start the API in a second terminal:

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

Open `http://localhost:3000/login`. Enter any username and password, then
choose the single role you want to preview (Retailer, Seller/Wholesaler, Driver,
or Admin). Local UI preview is enabled in `.env.example`; no password is stored
and the preview session resets on refresh.
Set `NEXT_PUBLIC_DEMO_MODE=false` in deployed environments.

## Implemented backend integration

- `POST /api/v1/procurement/parse` powers the retailer Procurement Copilot.
- `POST /api/v1/offers` and `GET /api/v1/offers?request_id=...` power the
  structured Offers workspace.
- Backend errors remain visible and form values are preserved; no request is
  represented as a completed order or payment.

Identity, catalog, pools, orders, fulfillment, seller, driver, and admin APIs
are not implemented in the backend yet. Their corresponding role pages are
deliberately rendered as integration-pending states rather than mock records.

The browser never computes an authoritative landed price, clears an allocation,
changes `C_max`, or stores credentials/payment tokens.
