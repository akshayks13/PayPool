"use client";

import Link from "next/link";
import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Clock3,
  Package,
  RefreshCw,
  ShieldCheck,
  Truck,
  Users,
} from "lucide-react";
import { useSession } from "@/components/providers";
import { request } from "@/lib/http";
import {
  money,
  type Allocation,
  type Audit,
  type BuyingRequest,
  type Order,
  type Pool,
  type Product,
  type Workspace,
} from "@/lib/commerce";
import type { Role } from "@/lib/roles";
import { PlatformFeatures } from "@/components/platform-features";
import type { Features } from "@/lib/features";
import { ConnectedCopilot } from "@/components/connected-copilot";
import {
  BusinessProfile,
  SellerReviewQueue,
} from "@/components/business-profile";
import { ImageUpload } from "@/components/image-upload";

type Act = (
  path: string,
  data?: unknown,
  headers?: Record<string, string>,
) => Promise<unknown>;
type Common = { data: Workspace; act: Act; busy: boolean };
export function Badge({ value }: { value: string }) {
  const bad = /FAILED|EXCEPTION|RECONCILIATION|CANCEL|EXCLUDED|EXPIRED/.test(
    value,
  );
  const good = /CAPTURED|MATCHED|COMPLETED|CLEARED|AUTHORIZED|DELIVERED/.test(
    value,
  );
  return (
    <span
      className={`inline-flex self-start items-center whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-bold tracking-wide ${bad ? "bg-rose-50 text-rose-800" : good ? "bg-emerald-50 text-emerald-800" : "bg-blue-50 text-blue-800"}`}
    >
      {value.replaceAll("_", " ")}
    </span>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <div className="card py-12 text-center text-sm text-slate-500">{text}</div>
  );
}
function Metric({
  title,
  value,
  icon,
}: {
  title: string;
  value: string | number;
  icon: ReactNode;
}) {
  return (
    <div className="card">
      <div className="flex justify-between text-sm text-slate-500">
        {title}
        <span className="text-blue-600">{icon}</span>
      </div>
      <div className="mt-3 text-3xl font-black text-ink">{value}</div>
    </div>
  );
}

export function CommerceWorkspace({
  role,
  section,
}: {
  role: Role;
  section: string;
}) {
  const { user, paymentProvider, isPreview } = useSession();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["workspace", user?.id],
    queryFn: () => request<Workspace>("/api/v1/workspace"),
    enabled: Boolean(user),
    refetchInterval: 5000,
    retry: false,
  });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const returned = useRef(false);
  const act: Act = async (path, payload = {}, headers) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const value = await request<Record<string, unknown>>(path, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });
      if (value.payment_error || value.error)
        setError(String(value.payment_error || value.error));
      else setNotice("Saved. The workspace reflects the latest server state.");
      await client.invalidateQueries({ queryKey: ["workspace"] });
      return value;
    } catch (e) {
      const message = e instanceof Error ? e.message : "Action failed";
      setError(message);
      throw e;
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    const approved = new URLSearchParams(window.location.search).get(
      "approved",
    );
    if (approved && user && !returned.current) {
      returned.current = true;
      act(`/api/v1/orders/${encodeURIComponent(approved)}/authorize`).catch(
        () => {},
      );
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [user]); // Payment operation is independently idempotent on the server.
  if (query.isLoading) return <Empty text="Loading your buying workspace…" />;
  if (query.error || !query.data)
    return (
      <div className="card text-red-800">
        {query.error instanceof Error
          ? query.error.message
          : "Workspace unavailable"}
        <button className="btn-secondary ml-4" onClick={() => query.refetch()}>
          Retry
        </button>
      </div>
    );
  const data = query.data;
  const common = { data, act, busy };
  let content: ReactNode;
  if (
    [
      "offers",
      "standing-orders",
      "inventory",
      "fleet",
      "service-areas",
      "agent-access",
      "product-feed",
    ].includes(section) ||
    (role === "ADMIN" &&
      ["integrations", "environment", "jobs"].includes(section))
  )
    content = <PlatformFeatures {...common} role={role} section={section} />;
  else if (section === "procurement")
    content = <ConnectedCopilot {...common} />;
  else if (["catalog", "inventory", "pricing"].includes(section))
    content = <Catalog {...common} seller={role === "SELLER"} />;
  else if (section === "upload-products") content = <ImportSheet {...common} />;
  else if (["pools", "operations", "dispatch"].includes(section))
    content = (
      <Pools
        {...common}
        data={{
          ...data,
          pools:
            section === "dispatch"
              ? data.pools.filter((p) => p.status === "CLEARED")
              : data.pools,
        }}
        role={role}
      />
    );
  else if (["requests", "offers"].includes(section))
    content = <Requests {...common} seller={role === "SELLER"} />;
  else if (
    ["orders", "stops", "pod", "exceptions", "completed"].includes(section) ||
    (!section && role === "DRIVER")
  )
    content = (
      <Orders
        {...common}
        data={{
          ...data,
          orders:
            section === "exceptions"
              ? data.orders.filter(
                  (o) =>
                    o.status === "DELIVERY_EXCEPTION" ||
                    o.payment_status === "REQUIRES_RECONCILIATION",
                )
              : section === "completed"
                ? data.orders.filter((o) =>
                    ["DELIVERED", "CANCELLED"].includes(o.status),
                  )
                : data.orders,
        }}
        role={role}
      />
    );
  else if (section === "receipts") content = <Receipts data={data} />;
  else if (["service-areas", "fleet"].includes(section))
    content = <Zones {...common} />;
  else if (["settings", "profile"].includes(section))
    content = <Settings {...common} />;
  else if (
    [
      "audit",
      "notifications",
      "integrations",
      "environment",
      "users",
      "seller-verification",
    ].includes(section)
  )
    content = <Operations {...common} section={section} />;
  else content = <Overview {...common} role={role} />;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-xs text-blue-900">
        <span>
          <b>{isPreview ? "Demo businesses & catalog" : "Connected account"}</b>{" "}
          ·{" "}
          {paymentProvider === "demo"
            ? "Offline payment simulation — no money moves"
            : "PayPal sandbox — test payments"}
        </span>
        <button
          onClick={() => query.refetch()}
          className="inline-flex items-center gap-2 font-semibold"
        >
          <RefreshCw size={13} /> Refresh
        </button>
      </div>
      {error && (
        <p
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"
        >
          {error}
        </p>
      )}
      {notice && (
        <p
          role="status"
          className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900"
        >
          {notice}
        </p>
      )}
      {content}
    </div>
  );
}

function Overview({ data, role }: Common & { role: Role }) {
  return (
    <div className="space-y-6">
      <section className="rounded-2xl bg-ink p-7 text-white">
        <p className="text-xs font-bold uppercase tracking-widest text-blue-200">
          Your next delivery, together
        </p>
        <h2 className="mt-3 text-2xl font-black">
          {role === "RETAILER"
            ? "Buy what your shop needs. Keep your price limit."
            : role === "SELLER"
              ? "Turn nearby demand into a viable delivery run."
              : "Every agreement. Every payment. One clear record."}
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
          Shared demand can unlock a supplier tier and spread delivery costs.
          Every final allocation is checked against the buyer’s ceiling, then
          explicitly approved.
        </p>
        <Link
          className="btn-primary mt-5"
          href={
            role === "RETAILER"
              ? "/retailer/procurement"
              : role === "SELLER"
                ? "/seller/pools"
                : "/admin/operations"
          }
        >
          {role === "RETAILER"
            ? "Create a buying request"
            : "Open delivery pools"}
        </Link>
      </section>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          title="Buying requests"
          value={data.requests.length}
          icon={<Package size={17} />}
        />
        <Metric
          title="Active delivery pools"
          value={
            data.pools.filter((p) =>
              ["ACCUMULATING", "CLEARED", "DISPATCHED"].includes(p.status),
            ).length
          }
          icon={<Users size={17} />}
        />
        <Metric
          title="Authorized orders"
          value={
            data.orders.filter((o) => o.payment_status === "AUTHORIZED").length
          }
          icon={<ShieldCheck size={17} />}
        />
        <Metric
          title="Matched receipts"
          value={data.receipts.filter((r) => r.status === "MATCHED").length}
          icon={<CheckCircle2 size={17} />}
        />
      </div>
      <Pools
        data={data}
        act={async () => {}}
        busy={false}
        role={role}
        readOnly
      />
    </div>
  );
}

function ProductImage({ product }: { product: Product }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [product.image_url]);
  return (
    <div className="mb-4 flex h-28 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
      {product.image_url && !failed ? (
        <img
          src={product.image_url}
          alt={product.title}
          loading="lazy"
          className="h-full max-w-full rounded-xl object-contain"
          onError={() => setFailed(true)}
        />
      ) : (
        <Package size={30} />
      )}
    </div>
  );
}

function Catalog({ data, act, busy, seller }: Common & { seller: boolean }) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Product | null>(null);
  const [editing, setEditing] = useState<Product | null>(null);
  const [category, setCategory] = useState("");
  const [brand, setBrand] = useState("");
  const [unit, setUnit] = useState("");
  const [supplier, setSupplier] = useState("");
  const [currency, setCurrency] = useState("");
  const [inStock, setInStock] = useState(true);
  const [page, setPage] = useState(0);
  useEffect(() => {
    setPage(0);
  }, [search, category, brand, unit, supplier, currency, inStock]);
  const catalog = useQuery({
    queryKey: [
      "catalog-search",
      data.user.id,
      search,
      category,
      brand,
      unit,
      supplier,
      currency,
      inStock,
      page,
    ],
    queryFn: () =>
      request<{
        items: Product[];
        total: number;
        engine: string;
        warning: string | null;
        as_of: string;
      }>(
        `/api/v1/catalog/search?${new URLSearchParams({ q: search, category, brand, unit, seller_id: supplier, currency, in_stock: String(inStock), offset: String(page * 20), limit: "20" })}`,
      ),
    enabled: !seller,
    refetchInterval: 5000,
  });
  const items = seller
    ? data.products.filter(
        (p) =>
          p.seller_id === data.user.id &&
          p.title.toLowerCase().includes(search.toLowerCase()),
      )
    : (catalog.data?.items ?? []);
  return (
    <div className="space-y-5">
      <div className="card flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">
            {seller
              ? "Your supplier catalog"
              : "Products delivered to your shop"}
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Prices shown are supplier tiers. Final delivery allocation is
            checked at clearing.
          </p>
        </div>
        <input
          aria-label="Search products"
          placeholder="Search products…"
          className="field !mt-0 max-w-xs"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      {!seller && (
        <div className="flex flex-wrap items-center gap-3">
          <select
            aria-label="Filter product category"
            className="field !mt-0 !w-auto"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">All categories</option>
            {Array.from(
              new Set(data.products.map((p) => p.category ?? "General")),
            ).map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          {[
            {
              label: "brand",
              value: brand,
              set: setBrand,
              values: Array.from(
                new Set(
                  data.products.map((p) => p.attributes.brand).filter(Boolean),
                ),
              ),
            },
            {
              label: "unit",
              value: unit,
              set: setUnit,
              values: Array.from(new Set(data.products.map((p) => p.unit))),
            },
            {
              label: "currency",
              value: currency,
              set: setCurrency,
              values: Array.from(new Set(data.products.map((p) => p.currency))),
            },
          ].map((f) => (
            <select
              className="field !mt-0 !w-auto"
              aria-label={`Filter product ${f.label}`}
              key={f.label}
              value={f.value}
              onChange={(e) => f.set(e.target.value)}
            >
              <option value="">
                All {f.label === "currency" ? "currencies" : `${f.label}s`}
              </option>
              {f.values.sort().map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          ))}
          <select
            aria-label="Filter product supplier"
            className="field !mt-0 !w-auto"
            value={supplier}
            onChange={(e) => setSupplier(e.target.value)}
          >
            <option value="">All suppliers</option>
            {Array.from(new Set(data.products.map((p) => p.seller_id))).map(
              (id) => (
                <option value={id} key={id}>
                  {data.people.find((p) => p.id === id)?.name ?? id}
                </option>
              ),
            )}
          </select>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={inStock}
              onChange={(e) => setInStock(e.target.checked)}
            />
            In stock only
          </label>
          {catalog.isLoading && (
            <p className="text-xs text-slate-500">
              Searching current supplier inventory…
            </p>
          )}
          {catalog.error && (
            <p role="alert" className="text-sm text-red-800">
              {catalog.error.message}
            </p>
          )}
          {catalog.data?.warning && (
            <p className="text-xs text-amber-800">{catalog.data.warning}</p>
          )}
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {items.map((p) => (
          <article className="card" key={p.id}>
            <ProductImage product={p} />
            <h3 className="font-bold">{p.title}</h3>
            <p className="mt-1 text-xs text-slate-500">
              {data.people.find((s) => s.id === p.seller_id)?.name ??
                p.seller_id}{" "}
              · {p.currency} · {p.attributes.brand ?? "Brand not specified"}
            </p>
            {p.description && (
              <p className="mt-2 text-sm leading-6 text-slate-500">
                {p.description}
              </p>
            )}
            {p.pack && <p className="mt-1 text-xs text-slate-500">{p.pack}</p>}
            <p className="mt-2 text-xs text-slate-500">
              {p.available_stock} {p.unit} available · {p.weight_grams} g / unit
            </p>
            {p.stock_updated_at && (
              <p className="mt-1 text-xs text-slate-500">
                Stock updated {new Date(p.stock_updated_at).toLocaleString()}
              </p>
            )}
            <div className="my-4 space-y-2">
              {p.tiers.map((t) => (
                <div
                  className="flex justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"
                  key={t.minimum_quantity}
                >
                  <span>
                    {t.minimum_quantity}+ {p.unit}
                  </span>
                  <b>
                    {money(t.unit_price_minor, p.currency)} / {p.unit}
                  </b>
                </div>
              ))}
            </div>
            <p className="mb-4 text-xs text-slate-500">
              {Object.entries(p.attributes)
                .map(([k, v]) => `${k}: ${v}`)
                .join(" · ")}
            </p>
            <button
              className="btn-primary w-full"
              onClick={() => (seller ? setEditing(p) : setSelected(p))}
            >
              {seller ? "Edit product & tiers" : "Prepare buying request"}
            </button>
          </article>
        ))}
      </div>
      {!seller && catalog.data && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
          <button
            className="btn-secondary"
            disabled={page === 0 || catalog.isFetching}
            onClick={() => setPage(page - 1)}
          >
            Previous products
          </button>
          <p>
            {catalog.data.total} products · Page {page + 1} · Checked{" "}
            {new Date(catalog.data.as_of).toLocaleTimeString()}
          </p>
          <button
            className="btn-secondary"
            disabled={
              (page + 1) * 20 >= catalog.data.total || catalog.isFetching
            }
            onClick={() => setPage(page + 1)}
          >
            Next products
          </button>
        </div>
      )}
      {!items.length && (
        <Empty text="No matching products in your delivery area." />
      )}
      {selected && (
        <section className="card">
          <div className="flex justify-between">
            <h3 className="text-lg font-bold">Request {selected.title}</h3>
            <button onClick={() => setSelected(null)}>Close</button>
          </div>
          <BuyingForm
            data={data}
            product={selected}
            act={act}
            busy={busy}
            onDone={() => setSelected(null)}
          />
        </section>
      )}
      {seller && (
        <ProductForm
          key={editing?.id ?? "new"}
          data={data}
          product={editing}
          act={act}
          busy={busy}
          onDone={() => setEditing(null)}
        />
      )}
    </div>
  );
}

export function BuyingForm({
  data,
  product,
  act,
  busy,
  onDone,
  initialQuantity = 30,
  initialCeiling,
  initialTarget,
  initialDate,
}: Common & {
  product: Product;
  onDone: () => void;
  initialQuantity?: number;
  initialCeiling?: number;
  initialTarget?: number;
  initialDate?: string;
}) {
  const zones = data.zones.filter(
    (z) =>
      z.seller_id === product.seller_id &&
      (z.currency ?? "USD") === product.currency,
  );
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const alternatives = data.products.filter(
    (p) =>
      p.id !== product.id &&
      p.seller_id === product.seller_id &&
      p.unit === product.unit &&
      p.currency === product.currency &&
      (p.pack ?? "") === (product.pack ?? "") &&
      Array.from(
        new Set([
          ...Object.keys(product.attributes),
          ...Object.keys(p.attributes),
        ]),
      )
        .filter((k) => k !== "brand")
        .every((k) => p.attributes[k] === product.attributes[k]),
  );
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await act("/api/v1/procurement/requests", {
        product_id: product.id,
        zone_id: form.get("zone"),
        dispatch_date: form.get("date"),
        quantity_min: Number(form.get("min")),
        quantity_max: Number(form.get("max")),
        ceiling_minor: Math.round(Number(form.get("ceiling")) * 100),
        target_price_minor: form.get("target")
          ? Math.round(Number(form.get("target")) * 100)
          : null,
        substitute_product_ids: form.getAll("substitute"),
        note: String(form.get("note") ?? ""),
      });
      onDone();
    } catch {}
  }
  return (
    <form onSubmit={submit} className="mt-5 grid gap-4 md:grid-cols-2">
      <label className="label">
        Delivery area
        <select className="field" name="zone" required>
          {zones.map((z) => (
            <option key={z.id} value={z.id}>
              {z.name}
            </option>
          ))}
        </select>
      </label>
      <label className="label">
        Delivery date
        <input
          className="field"
          type="date"
          name="date"
          defaultValue={initialDate ?? tomorrow}
          min={new Date().toISOString().slice(0, 10)}
          required
        />
      </label>
      <label className="label">
        Minimum quantity ({product.unit})
        <input
          className="field"
          name="min"
          type="number"
          min="1"
          max="5000"
          defaultValue={initialQuantity}
          required
        />
      </label>
      <label className="label">
        Maximum quantity ({product.unit})
        <input
          className="field"
          name="max"
          type="number"
          min="1"
          max="5000"
          defaultValue={initialQuantity}
          required
        />
      </label>
      <label className="label">
        Hard delivered-price ceiling ({product.currency} / {product.unit})
        <input
          className="field"
          name="ceiling"
          type="number"
          step="0.01"
          min="0.01"
          defaultValue={
            initialCeiling ??
            (product.tiers[0].unit_price_minor +
              Math.ceil(
                ((zones[0]?.base_freight_minor ?? 0) +
                  (zones[0]?.stop_fee_minor ?? 0)) /
                  initialQuantity,
              )) /
              100
          }
          required
        />
        <span className="mt-1 block text-xs font-normal text-slate-500">
          Includes your freight share. A low ceiling may need more buyers before
          it becomes feasible.
        </span>
      </label>
      <label className="label">
        Target delivered price (optional, {product.currency} / {product.unit})
        <input
          className="field"
          name="target"
          defaultValue={initialTarget}
          type="number"
          min="0.01"
          step="0.01"
          placeholder="Preferred price, below your hard limit"
        />
      </label>
      <label className="label">
        Notes
        <input
          className="field"
          name="note"
          maxLength={1000}
          placeholder="Delivery instructions…"
        />
      </label>
      {alternatives.length > 0 && (
        <fieldset className="rounded-xl border p-4 md:col-span-2">
          <legend className="px-2 text-sm font-bold">
            Optional, explicitly approved substitutes
          </legend>
          {alternatives.map((p) => (
            <label key={p.id} className="mt-2 flex gap-2 text-sm">
              <input type="checkbox" name="substitute" value={p.id} /> {p.title}
            </label>
          ))}
        </fieldset>
      )}
      <div className="md:col-span-2">
        <button className="btn-primary" disabled={busy || !zones.length}>
          {busy ? "Submitting…" : "Confirm request & join delivery pool"}
        </button>
        <p className="mt-2 text-xs text-slate-500">
          This creates a buying request. You approve the exact final amount
          separately after the pool clears.
        </p>
      </div>
    </form>
  );
}

function Requests({ data, act, busy, seller }: Common & { seller: boolean }) {
  if (!data.requests.length)
    return (
      <Empty text="No buying requests yet. Retailers can create one from the catalog or buying helper." />
    );
  return (
    <div className="space-y-4">
      {data.requests.map((r) => (
        <article key={r.id} className="card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <b>
                {data.products.find((p) => p.id === r.product_id)?.title ??
                  r.product_id}
              </b>
              <p className="mt-1 text-sm text-slate-500">
                {r.quantity_min}–{r.quantity_max} units · by {r.dispatch_date} ·{" "}
                {seller ? r.buyer_id : "Your request"}
              </p>
            </div>
            <Badge value={r.status} />
          </div>
          <div className="mt-4 text-sm">
            Maximum delivered unit price:{" "}
            <b>{money(r.ceiling_minor, r.currency)}</b>
            {r.target_price_minor != null && (
              <p className="mt-1 text-xs text-slate-500">
                Preferred target {money(r.target_price_minor, r.currency)} /
                unit; the hard ceiling remains binding.
              </p>
            )}
          </div>
          <div className="mt-4 flex gap-2">
            <Link
              className="btn-secondary"
              href={seller ? "/seller/pools" : "/retailer/pools"}
            >
              View shared delivery
            </Link>
            {!seller &&
              r.status === "ACTIVE" &&
              ["ACCUMULATING", "FAILED"].includes(
                data.pools.find((p) => p.id === r.pool_id)?.status ?? "",
              ) && (
                <button
                  disabled={busy}
                  className="btn-secondary"
                  onClick={() =>
                    act(`/api/v1/procurement/requests/${r.id}/withdraw`).catch(
                      () => {},
                    )
                  }
                >
                  Withdraw request
                </button>
              )}
          </div>
        </article>
      ))}
    </div>
  );
}

function Pools({
  data,
  act,
  busy,
  role,
  readOnly = false,
}: Common & { role: Role; readOnly?: boolean }) {
  const [driver, setDriver] = useState("driver-demo");
  const [vehicle, setVehicle] = useState("");
  const fleet = useQuery({
    queryKey: ["features", data.user.id],
    queryFn: () => request<Features>("/api/v1/features"),
    enabled: !readOnly && ["SELLER", "ADMIN"].includes(role),
  });
  const vehicles =
    fleet.data?.vehicles.filter(
      (v) => v.seller_id === data.pools[0]?.seller_id && v.active,
    ) ?? [];
  const [exclude, setExclude] = useState<Record<string, string>>({});
  if (!data.pools.length)
    return (
      <Empty text="No delivery pools yet. Confirm a retailer request to begin collecting shared demand." />
    );
  return (
    <div className="space-y-5">
      {data.pools
        .slice()
        .reverse()
        .map((p) => (
          <section className="card" key={p.id}>
            <div className="flex flex-wrap justify-between gap-3">
              <div>
                {p.example_label && (
                  <p className="mb-2 text-sm font-semibold text-teal-700">
                    {p.example_label}
                  </p>
                )}
                <p className="text-xs font-bold uppercase tracking-wider text-blue-600">
                  Delivery run · version {p.version}
                </p>
                <h3 className="mt-1 text-xl font-black">
                  {p.zone_snapshot?.name ??
                    data.zones.find((z) => z.id === p.zone_id)?.name ??
                    "Shared delivery"}
                </h3>
                <p className="mt-1 text-sm text-slate-500">
                  {p.dispatch_date} · {p.member_count} participating requests ·{" "}
                  {p.included_count} cleared
                  {p.delivery_window ? ` · ${p.delivery_window}` : ""}
                </p>
              </div>
              <Badge value={p.status} />
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl bg-slate-50 p-3 text-sm">
                <span className="block text-xs text-slate-500">
                  Total route freight
                </span>
                <b>
                  {p.freight_minor !== undefined
                    ? money(p.freight_minor, p.currency)
                    : "Calculated at clearing"}
                </b>
              </div>
              <div className="rounded-xl bg-slate-50 p-3 text-sm">
                <span className="block text-xs text-slate-500">
                  Allocated weight
                </span>
                <b>
                  {p.weight_grams !== undefined
                    ? `${p.weight_grams / 1000} kg`
                    : "Accumulating demand"}
                </b>
              </div>
              <div className="rounded-xl bg-slate-50 p-3 text-sm">
                <span className="block text-xs text-slate-500">
                  Buyer authorizations
                </span>
                <b>
                  {p.authorized_count} / {p.included_count}
                </b>
              </div>
            </div>
            {p.cutoff_at && (
              <p className="mt-3 text-xs text-slate-500">
                Buying cutoff: {new Date(p.cutoff_at).toLocaleString()}
              </p>
            )}
            {p.approval_expires_at && p.status === "CLEARED" && (
              <p className="mt-2 text-xs text-amber-800">
                Final approval expires{" "}
                {new Date(p.approval_expires_at).toLocaleString()}
              </p>
            )}
            {p.reason && (
              <p className="mt-4 text-sm leading-6 text-slate-600">
                {p.reason}
              </p>
            )}
            {p.agreement_hash && (
              <p
                className="mt-2 break-all font-mono text-[10px] text-slate-400"
                title={p.agreement_hash}
              >
                Agreement {p.agreement_hash.slice(0, 24)}… · {p.solver}
              </p>
            )}
            {p.allocations.length > 0 && (
              <div className="mt-5 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b text-xs text-slate-500">
                      {[
                        "Retailer / item",
                        "Quantity",
                        "Unit price",
                        "Freight",
                        "Total",
                        "Ceiling / unit",
                      ].map((h) => (
                        <th key={h} className="px-2 py-3">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {p.allocations.map((a) => (
                      <tr key={a.request_id} className="border-b">
                        <td className="px-2 py-3">
                          <b>
                            {data.people.find((u) => u.id === a.buyer_id)
                              ?.name ?? a.buyer_id}
                          </b>
                          <span className="block text-xs text-slate-500">
                            {a.product_snapshot?.title ??
                              data.products.find((i) => i.id === a.product_id)
                                ?.title}
                            {a.substituted ? " · approved substitute" : ""}
                          </span>
                        </td>
                        <td className="px-2">{a.quantity}</td>
                        <td className="px-2">
                          {money(a.unit_price_minor, a.currency)}
                        </td>
                        <td className="px-2">
                          {money(a.freight_minor, a.currency)}
                        </td>
                        <td className="px-2 font-bold">
                          {money(a.total_minor, a.currency)}
                        </td>
                        <td className="px-2">
                          {money(a.ceiling_minor, a.currency)}
                          {a.target_price_minor != null && (
                            <p className="mt-1 text-xs text-slate-500">
                              Target {money(a.target_price_minor, a.currency)} ·{" "}
                              {a.total_minor <=
                              a.target_price_minor * a.quantity
                                ? "Target met"
                                : "Above preferred target"}
                            </p>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {!readOnly && (
              <div className="mt-5 flex flex-wrap items-center gap-3">
                {["SELLER", "ADMIN"].includes(role) &&
                  ["ACCUMULATING", "FAILED", "LOCKED"].includes(p.status) && (
                    <button
                      className="btn-primary"
                      disabled={busy}
                      onClick={() =>
                        act(`/api/v1/pools/${p.id}/clear`).catch(() => {})
                      }
                    >
                      Optimize & lock final quote
                    </button>
                  )}
                {role === "RETAILER" &&
                  p.status === "CLEARED" &&
                  p.allocations.some((a) => a.buyer_id === data.user.id) &&
                  !data.orders.some(
                    (o) => o.pool_id === p.id && o.buyer_id === data.user.id,
                  ) && (
                    <button
                      className="btn-primary"
                      disabled={busy}
                      onClick={() =>
                        act(`/api/v1/pools/${p.id}/approve`, {
                          version: p.version,
                        }).catch(() => {})
                      }
                    >
                      Approve my allocation · version {p.version}
                    </button>
                  )}
                {role === "RETAILER" &&
                  data.orders.some((o) => o.pool_id === p.id) && (
                    <Link className="btn-primary" href="/retailer/orders">
                      Continue to payment
                    </Link>
                  )}
                {["SELLER", "ADMIN"].includes(role) &&
                  p.status === "CLEARED" && (
                    <>
                      <select
                        aria-label="Assign driver"
                        className="field !mt-0 !w-auto"
                        value={driver}
                        onChange={(e) => setDriver(e.target.value)}
                      >
                        {data.people
                          .filter(
                            (u) =>
                              u.roles.includes("DRIVER") && u.active !== false,
                          )
                          .map((u) => (
                            <option value={u.id} key={u.id}>
                              {u.name}
                            </option>
                          ))}
                      </select>
                      <select
                        aria-label="Assign vehicle"
                        className="field !mt-0 !w-auto"
                        value={vehicle || vehicles[0]?.id || ""}
                        onChange={(e) => setVehicle(e.target.value)}
                      >
                        {!vehicles.length && (
                          <option value="">Zone capacity (demo only)</option>
                        )}
                        {vehicles.map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.name} · {v.max_weight_grams / 1000} kg
                          </option>
                        ))}
                      </select>
                      <button
                        className="btn-primary"
                        disabled={
                          busy ||
                          p.authorized_count !== p.included_count ||
                          !p.included_count
                        }
                        onClick={() =>
                          act(`/api/v1/pools/${p.id}/dispatch`, {
                            driver_id: driver,
                            vehicle_id:
                              vehicle ||
                              vehicles.find((v) => v.seller_id === p.seller_id)
                                ?.id ||
                              null,
                          }).catch(() => {})
                        }
                      >
                        <Truck size={16} />
                        Dispatch authorized run
                      </button>
                    </>
                  )}
                {["SELLER", "ADMIN"].includes(role) &&
                  [
                    "CLEARED",
                    "ACCUMULATING",
                    "FAILED",
                    "CANCEL_PENDING",
                  ].includes(p.status) && (
                    <button
                      className="btn-secondary"
                      disabled={busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Cancel this delivery pool and release any uncaptured authorizations?",
                          )
                        )
                          act(`/api/v1/pools/${p.id}/cancel`).catch(() => {});
                      }}
                    >
                      Cancel & release commitments
                    </button>
                  )}
              </div>
            )}
            {!readOnly &&
              ["SELLER", "ADMIN"].includes(role) &&
              p.status === "CLEARED" && (
                <details className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <summary className="cursor-pointer text-sm font-bold text-amber-900">
                    Recover a changed order
                  </summary>
                  <p className="my-3 text-sm text-amber-900">
                    Release the old commitments, exclude a withdrawn request if
                    needed, and calculate a new quote. Every remaining buyer
                    must approve again.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <select
                      aria-label="Request to exclude"
                      className="field !mt-0 !w-auto"
                      value={exclude[p.id] ?? ""}
                      onChange={(e) =>
                        setExclude({ ...exclude, [p.id]: e.target.value })
                      }
                    >
                      <option value="">Keep all active requests</option>
                      {data.requests
                        .filter(
                          (r) => r.pool_id === p.id && r.status === "ACTIVE",
                        )
                        .map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.buyer_id} · {r.quantity_min} units
                          </option>
                        ))}
                    </select>
                    <button
                      className="btn-secondary"
                      disabled={busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Void old authorizations and require new buyer approvals?",
                          )
                        )
                          act(
                            `/api/v1/pools/${p.id}/replan?exclude_request_id=${encodeURIComponent(exclude[p.id] ?? "")}`,
                          ).catch(() => {});
                      }}
                    >
                      Recalculate with fresh approvals
                    </button>
                  </div>
                </details>
              )}
          </section>
        ))}
    </div>
  );
}

function Orders({ data, act, busy, role }: Common & { role: Role }) {
  if (!data.orders.length)
    return (
      <Empty text="No approved orders yet. Buyers first review and approve their cleared pool allocation." />
    );
  return (
    <div className="space-y-4">
      {role === "DRIVER" && <DriverRoute data={data} />}
      {data.orders
        .slice()
        .sort((a, b) => {
          if (role !== "DRIVER") return b.id.localeCompare(a.id);
          const pa = data.pools.find((p) => p.id === a.pool_id),
            pb = data.pools.find((p) => p.id === b.pool_id);
          return (
            a.pool_id.localeCompare(b.pool_id) ||
            (pa?.route?.indexOf(a.request_id) ?? 0) -
              (pb?.route?.indexOf(b.request_id) ?? 0)
          );
        })
        .map((o) => (
          <article className="card" key={o.id}>
            <div className="flex flex-wrap justify-between gap-3">
              <div>
                <h3 className="font-bold">
                  {o.product_snapshot?.title ??
                    data.products.find((p) => p.id === o.product_id)?.title ??
                    o.product_id}
                </h3>
                {role === "DRIVER" && (
                  <div className="mt-2 text-sm">
                    <b>
                      Deliver to{" "}
                      {o.buyer_name ??
                        data.people.find((p) => p.id === o.buyer_id)?.name ??
                        o.buyer_id}
                    </b>
                    {o.delivery_contact && (
                      <>
                        <p>
                          {[
                            o.delivery_contact.business_address,
                            o.delivery_contact.city,
                            o.delivery_contact.postal_code,
                            o.delivery_contact.country,
                          ]
                            .filter(Boolean)
                            .join(", ")}
                        </p>
                        <p>
                          {o.delivery_contact.contact_phone}{" "}
                          {o.delivery_contact.preferred_delivery_window}
                        </p>
                        <p>{o.delivery_contact.delivery_instructions}</p>
                      </>
                    )}
                  </div>
                )}
                <p className="mt-1 text-sm text-slate-500">
                  {o.quantity} units · {money(o.total_minor, o.currency)}{" "}
                  including {money(o.freight_minor, o.currency)} freight
                </p>
                <p className="mt-2 font-mono text-[10px] text-slate-400">
                  {o.id}
                </p>
              </div>
              <div className="space-x-2">
                <Badge value={o.status} />
                <Badge value={o.payment_status} />
              </div>
            </div>
            {o.provider_order_id && (
              <p className="mt-3 break-all text-xs text-slate-500">
                {o.provider === "demo"
                  ? "Simulated reference"
                  : "PayPal sandbox order"}
                : {o.provider_order_id}
              </p>
            )}
            {o.payment_error && (
              <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-800">
                {o.payment_error}
              </p>
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              {role === "RETAILER" && o.status === "AWAITING_CONFIRMATION" && (
                <button
                  className="btn-primary"
                  disabled={busy}
                  onClick={() => {
                    if (
                      window.confirm(
                        "Confirm that all ordered units arrived in acceptable condition? This allows the agreed payment capture.",
                      )
                    )
                      act(`/api/v1/orders/${o.id}/confirm-delivery`).catch(
                        () => {},
                      );
                  }}
                >
                  Confirm received goods & release payment
                </button>
              )}
              {role === "RETAILER" && o.payment_status === "NOT_STARTED" && (
                <button
                  className="btn-primary"
                  disabled={busy}
                  onClick={async () => {
                    try {
                      const result = (await act(
                        `/api/v1/orders/${o.id}/checkout`,
                      )) as Order;
                      if (result.approval_url)
                        window.location.assign(result.approval_url);
                    } catch {}
                  }}
                >
                  {data.payment_provider === "demo"
                    ? "Create simulated checkout"
                    : "Continue to PayPal sandbox"}
                </button>
              )}
              {role === "RETAILER" && o.payment_status === "CREATED" && (
                <>
                  {o.approval_url && (
                    <a className="btn-primary" href={o.approval_url}>
                      Open PayPal approval
                    </a>
                  )}
                  <button
                    className="btn-secondary"
                    disabled={busy}
                    onClick={() =>
                      act(`/api/v1/orders/${o.id}/authorize`).catch(() => {})
                    }
                  >
                    {data.payment_provider === "demo"
                      ? "Simulate buyer authorization"
                      : "Confirm PayPal authorization"}
                  </button>
                </>
              )}
              {o.payment_status === "AUTHORIZED" && (
                <p className="flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-900">
                  <ShieldCheck size={16} />
                  Authorized. Capture follows complete acknowledged delivery.
                </p>
              )}
              {[
                "REQUIRES_RECONCILIATION",
                "CAPTURE_PENDING",
                "REFUND_PENDING",
              ].includes(o.payment_status) && (
                <button
                  className="btn-secondary"
                  disabled={busy}
                  onClick={() =>
                    act(`/api/v1/orders/${o.id}/reconcile`).catch(() => {})
                  }
                >
                  Reconcile provider status
                </button>
              )}
              {["SELLER", "ADMIN", "DRIVER"].includes(role) &&
                o.pod &&
                !o.pod.exception &&
                o.payment_status === "AUTHORIZED" && (
                  <button
                    className="btn-secondary"
                    disabled={busy}
                    onClick={() =>
                      act(`/api/v1/orders/${o.id}/capture`).catch(() => {})
                    }
                  >
                    Retry delivery capture
                  </button>
                )}
              {["SELLER", "ADMIN"].includes(role) &&
                ["CAPTURED", "PARTIALLY_REFUNDED"].includes(
                  o.payment_status,
                ) && (
                  <button
                    className="btn-secondary"
                    disabled={busy}
                    onClick={async () => {
                      if (
                        !window.confirm(
                          `Refund the remaining ${money(o.total_minor - o.refunded_minor, o.currency)}?`,
                        )
                      )
                        return;
                      try {
                        await act(
                          `/api/v1/orders/${o.id}/refund`,
                          {
                            amount_minor: o.total_minor - o.refunded_minor,
                            reason: "Merchant-approved remaining refund",
                          },
                          {
                            "Idempotency-Key": `refund-remaining-${o.id}-${o.refunded_minor}`,
                          },
                        );
                      } catch {}
                    }}
                  >
                    Refund remaining amount
                  </button>
                )}
            </div>
            {["SELLER", "ADMIN"].includes(role) &&
              o.status === "DELIVERY_EXCEPTION" && (
                <ExceptionForm order={o} act={act} busy={busy} />
              )}
            {!!o.pod_history?.length && (
              <details className="mt-4 rounded-xl border p-3 text-sm">
                <summary>
                  Previous delivery attempts ({o.pod_history.length})
                </summary>
                {o.pod_history.map((h) => (
                  <p key={h.id} className="mt-2 text-xs text-slate-500">
                    {h.pod.delivered_quantity} units · {h.pod.exception} ·{" "}
                    {h.reason}
                  </p>
                ))}
              </details>
            )}
            {role === "DRIVER" && !o.pod && o.status === "FULFILLING" && (
              <PodForm order={o} act={act} busy={busy} />
            )}
            {o.pod && (
              <div className="mt-4 rounded-xl bg-slate-50 p-4 text-sm">
                <b>Delivery evidence</b>
                {o.pod.evidence_media_id && (
                  <a
                    className="mt-2 block text-blue-700 underline"
                    href={`/api/v1/media/${o.pod.evidence_media_id}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    View delivery photo
                  </a>
                )}
                <p className="mt-1">
                  {o.pod.delivered_quantity} units · acknowledged by{" "}
                  {o.pod.recipient_name} ·{" "}
                  {new Date(o.pod.recorded_at).toLocaleString()}
                </p>
                {o.pod.exception && (
                  <p className="mt-1 text-rose-800">
                    {o.pod.exception}: {o.pod.note}
                  </p>
                )}
              </div>
            )}
          </article>
        ))}
    </div>
  );
}

function PodForm({
  order,
  act,
  busy,
}: {
  order: Order;
  act: Act;
  busy: boolean;
}) {
  const [evidence, setEvidence] = useState<string | null>(null);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await act(`/api/v1/orders/${order.id}/pod`, {
        delivered_quantity: Number(f.get("quantity")),
        recipient_name: f.get("recipient"),
        acknowledgement: f.get("ack") === "on",
        exception: f.get("exception") || null,
        note: f.get("note"),
        evidence_media_id: evidence,
      });
    } catch {}
  }
  return (
    <form
      onSubmit={submit}
      className="mt-5 grid gap-4 rounded-xl border p-4 sm:grid-cols-2"
    >
      <ImageUpload
        path={`/api/v1/orders/${order.id}/evidence-image`}
        label="Upload delivery photo"
        onUploaded={(image) => setEvidence(image.id)}
      />
      {evidence && (
        <a
          className="text-sm text-blue-700 underline"
          href={`/api/v1/media/${evidence}`}
          target="_blank"
          rel="noreferrer"
        >
          View attached delivery photo
        </a>
      )}
      <label className="label">
        {order.pod_history?.length
          ? "Total good units received across attempts"
          : "Delivered quantity"}
        <input
          className="field"
          type="number"
          name="quantity"
          min="0"
          max={order.quantity}
          defaultValue={order.quantity}
          required
        />
      </label>
      <label className="label">
        Recipient name
        <input
          className="field"
          name="recipient"
          minLength={2}
          maxLength={100}
          required
        />
      </label>
      <label className="label">
        Delivery exception
        <select className="field" name="exception">
          <option value="">Complete delivery</option>
          {[
            "DAMAGED",
            "MISSING_ITEMS",
            "RECIPIENT_UNAVAILABLE",
            "REFUSED",
            "ADDRESS_ISSUE",
            "OTHER",
          ].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
      </label>
      <label className="label">
        Notes
        <input className="field" name="note" maxLength={1000} />
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" name="ack" />
        Recipient acknowledges receipt
      </label>
      <button className="btn-primary" disabled={busy}>
        Record delivery evidence
      </button>
    </form>
  );
}

function Receipts({ data }: { data: Workspace }) {
  return data.receipts.length ? (
    <div className="space-y-4">
      {data.receipts.map((r) => (
        <article className="card" key={r.id}>
          <div className="flex justify-between">
            <h3 className="font-bold">PayPool Smart Receipt</h3>
            <Badge value={r.status} />
          </div>
          <p className="mt-3 text-2xl font-black">
            {money(r.order.total_minor, r.order.currency)}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            {r.order.quantity} units · {r.order.payment_status} ·{" "}
            {r.order.pod
              ? "Delivery evidence recorded"
              : "Awaiting delivery evidence"}
          </p>
          <p className="mt-2 break-all font-mono text-[10px] text-slate-400">
            Agreement {r.order.agreement_hash}
          </p>
          <p className="mt-3 text-xs text-slate-500">{r.note}</p>
          <a
            className="btn-secondary mt-4 mr-3"
            href={`/api/v1/orders/${r.order.id}/receipt.html`}
            target="_blank"
            rel="noreferrer"
          >
            Open printable receipt
          </a>
          <button
            className="btn-secondary mt-4"
            onClick={() => {
              const url = URL.createObjectURL(
                new Blob([JSON.stringify(r, null, 2)], {
                  type: "application/json",
                }),
              );
              const a = document.createElement("a");
              a.href = url;
              a.download = `${r.id}.json`;
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            Download evidence record
          </button>
        </article>
      ))}
    </div>
  ) : (
    <Empty text="Receipts appear after a buyer approves an order. They are matched when payment and complete delivery agree." />
  );
}

function ProductForm({
  product,
  act,
  busy,
  onDone,
}: Common & { product: Product | null; onDone: () => void }) {
  const [error, setError] = useState("");
  const [imageUrl, setImageUrl] = useState(product?.image_url ?? "");
  const client = useQueryClient();
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      const payload = {
        title: f.get("title"),
        description: f.get("description"),
        category: f.get("category"),
        pack: f.get("pack"),
        image_url: imageUrl,
        product_url: f.get("public_url"),
        active: f.get("active") === "on",
        negotiation_floor_minor: f.get("floor")
          ? Math.round(Number(f.get("floor")) * 100)
          : null,
        unit: f.get("unit"),
        currency: f.get("currency"),
        stock: Number(f.get("stock")),
        weight_grams: Number(f.get("weight")),
        volume_cm3: Number(f.get("volume")),
        attributes: JSON.parse(String(f.get("attributes"))),
        tiers: JSON.parse(String(f.get("tiers"))),
      };
      if (product) {
        await request(`/api/v1/seller/products/${product.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        await client.invalidateQueries({ queryKey: ["workspace"] });
      } else await act("/api/v1/seller/products", payload);
      setError("");
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save product");
    }
  }
  return (
    <section className="card">
      <h3 className="text-lg font-bold">
        {product ? "Edit product" : "Add a catalog product"}
      </h3>
      <form onSubmit={submit} className="mt-4 grid gap-4 md:grid-cols-3">
        {product ? (
          <ImageUpload
            path={`/api/v1/seller/products/${product.id}/image`}
            label="Upload product photo"
            onUploaded={(image) => {
              setImageUrl(image.url);
              client.invalidateQueries({ queryKey: ["workspace"] });
            }}
          />
        ) : (
          <p className="text-xs text-slate-500 md:col-span-2">
            Save the product first to upload a photo, or provide a public HTTPS
            image URL below.
          </p>
        )}
        {[
          ["title", "Product name", product?.title ?? ""],
          ["description", "Description", product?.description ?? ""],
          ["category", "Category", product?.category ?? "General"],
          ["pack", "Pack / specification", product?.pack ?? ""],
          [
            "image",
            "Image URL (HTTPS or uploaded image)",
            product?.image_url ?? "",
          ],
          [
            "public_url",
            "Public product URL (HTTPS, optional)",
            product?.product_url ?? "",
          ],
          [
            "floor",
            "Negotiation floor (optional)",
            product?.negotiation_floor_minor
              ? String(product.negotiation_floor_minor / 100)
              : "",
          ],
          ["unit", "Selling unit", product?.unit ?? "kg"],
          ["currency", "Currency", product?.currency ?? "USD"],
          ["stock", "Units in stock", product?.stock ?? 100],
          ["weight", "Grams per unit", product?.weight_grams ?? 1000],
          ["volume", "Packed cm³ per unit", product?.volume_cm3 ?? 1500],
        ].map(([name, label, value]) => (
          <label className="label" key={name}>
            {label}
            <input
              className="field"
              name={String(name)}
              defaultValue={name === "image" ? undefined : value}
              value={name === "image" ? imageUrl : undefined}
              onChange={
                name === "image"
                  ? (e) => setImageUrl(e.target.value)
                  : undefined
              }
              type={
                ["stock", "weight", "volume"].includes(String(name))
                  ? "number"
                  : "text"
              }
              required={
                ![
                  "description",
                  "pack",
                  "image",
                  "public_url",
                  "floor",
                ].includes(String(name))
              }
            />
          </label>
        ))}
        <label className="flex items-center gap-2 text-sm md:col-span-3">
          <input
            name="active"
            type="checkbox"
            defaultChecked={product?.active ?? true}
          />
          Listed in active catalog
        </label>
        <label className="label md:col-span-3">
          Product attributes (JSON)
          <textarea
            className="field"
            name="attributes"
            defaultValue={JSON.stringify(
              product?.attributes ?? {
                variety: "Sona Masoori",
                brand: "Your brand",
              },
            )}
            required
          />
        </label>
        <label className="label md:col-span-3">
          Approved tax-inclusive tiers (integer cents per selling unit)
          <textarea
            className="field font-mono text-xs"
            name="tiers"
            defaultValue={JSON.stringify(
              product?.tiers ?? [
                { minimum_quantity: 1, unit_price_minor: 180 },
                { minimum_quantity: 60, unit_price_minor: 150 },
              ],
            )}
            required
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-800 md:col-span-3">
            {error}
          </p>
        )}
        <button className="btn-primary" disabled={busy}>
          Save supplier policy
        </button>
      </form>
    </section>
  );
}

function ImportSheet({ act }: Common) {
  const [preview, setPreview] = useState<{
    id: string;
    filename: string;
    products: Product[];
    errors: { row: number; message: string }[];
    status: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setPreview(
        await request("/api/v1/seller/imports/preview", {
          method: "POST",
          body: new FormData(e.currentTarget),
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card">
      <h2 className="text-xl font-bold">
        Review your product sheet before import
      </h2>
      <p className="mt-2 text-sm leading-6 text-slate-500">
        CSV or XLSX, up to 2 MB / 1,000 rows. Columns: product_name, price,
        stock, unit, currency, weight_grams, volume_cm3. Prices are major
        currency units; USD is the default.
      </p>
      <form className="mt-5 flex flex-wrap gap-3" onSubmit={upload}>
        <input
          aria-label="Product spreadsheet"
          type="file"
          name="file"
          accept=".csv,.xlsx"
          required
        />
        <button className="btn-primary" disabled={busy}>
          {busy ? "Reading…" : "Preview sheet"}
        </button>
      </form>
      {error && (
        <p role="alert" className="mt-4 text-red-800">
          {error}
        </p>
      )}
      {preview && (
        <div className="mt-6">
          <Badge value={preview.status} />
          <p className="mt-3 font-bold">
            {preview.products.length} valid products · {preview.errors.length}{" "}
            rows need correction
          </p>
          <div className="mt-3 max-h-64 overflow-auto rounded-xl bg-slate-50 p-4 text-sm">
            {preview.products.map((p, i) => (
              <p className="py-1" key={i}>
                {p.title} · {p.stock} {p.unit} ·{" "}
                {money(p.tiers[0].unit_price_minor, p.currency)}
              </p>
            ))}
            {preview.errors.map((e) => (
              <p className="py-1 text-red-800" key={e.row}>
                Row {e.row}: {e.message}
              </p>
            ))}
          </div>
          <button
            className="btn-primary mt-4"
            disabled={
              preview.status === "IMPORTED" || !preview.products.length || busy
            }
            onClick={async () => {
              try {
                await act(`/api/v1/seller/imports/${preview.id}/commit`);
                setPreview({ ...preview, status: "IMPORTED" });
              } catch {}
            }}
          >
            Confirm import of valid rows
          </button>
        </div>
      )}
    </section>
  );
}

function Zones({ data, act, busy }: Common) {
  const [error, setError] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await act("/api/v1/seller/zones", {
        name: f.get("name"),
        polygon: JSON.parse(String(f.get("polygon"))),
        depot: JSON.parse(String(f.get("depot"))),
        base_freight_minor: Math.round(Number(f.get("base")) * 100),
        stop_fee_minor: Math.round(Number(f.get("stop")) * 100),
        min_weight_grams: Number(f.get("min")) * 1000,
        max_weight_grams: Number(f.get("max")) * 1000,
        max_volume_cm3: Number(f.get("volume")),
      });
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invalid zone");
    }
  }
  return (
    <div className="space-y-5">
      {data.zones
        .filter((z) => z.seller_id === data.user.id)
        .map((z) => (
          <section className="card" key={z.id}>
            <h3 className="font-bold">{z.name}</h3>
            <p className="mt-2 text-sm text-slate-500">
              Base run {money(z.base_freight_minor, z.currency)} +{" "}
              {money(z.stop_fee_minor, z.currency)} / stop ·{" "}
              {z.min_weight_grams / 1000}–{z.max_weight_grams / 1000} kg ·{" "}
              {z.max_volume_cm3 / 1000000} m³
            </p>
            <svg
              viewBox="0 0 400 160"
              className="mt-4 h-40 w-full rounded-xl bg-blue-50"
              role="img"
              aria-label="Service area preview"
            >
              <polygon
                points={z.polygon
                  .map(([lon, lat]) => {
                    const xs = z.polygon.map((p) => p[0]),
                      ys = z.polygon.map((p) => p[1]);
                    return `${30 + ((lon - Math.min(...xs)) / (Math.max(...xs) - Math.min(...xs) || 1)) * 340},${140 - ((lat - Math.min(...ys)) / (Math.max(...ys) - Math.min(...ys) || 1)) * 120}`;
                  })
                  .join(" ")}
                fill="#bfdbfe"
                stroke="#2563eb"
                strokeWidth="2"
              />
            </svg>
            <p className="mt-2 text-xs text-slate-500">
              Longitude / latitude polygon. Boundary points are included.
            </p>
          </section>
        ))}
      <section className="card">
        <h3 className="font-bold">Add a delivery area & vehicle constraints</h3>
        <form onSubmit={submit} className="mt-4 grid gap-4 md:grid-cols-2">
          {[
            ["name", "Area name", "New delivery area"],
            ["base", "Base route fee (USD)", "6"],
            ["stop", "Per-stop fee (USD)", "1"],
            ["min", "Minimum dispatch weight (kg)", "50"],
            ["max", "Vehicle maximum weight (kg)", "200"],
            ["volume", "Vehicle packed capacity (cm³)", "400000"],
          ].map(([name, label, value]) => (
            <label className="label" key={name}>
              {label}
              <input
                name={name}
                className="field"
                defaultValue={value}
                required
              />
            </label>
          ))}
          <label className="label">
            Polygon coordinates [longitude, latitude]
            <textarea
              name="polygon"
              className="field font-mono text-xs"
              defaultValue="[[77.50,12.90],[77.70,12.90],[77.70,13.05],[77.50,13.05]]"
              required
            />
          </label>
          <label className="label">
            Distributor depot [longitude, latitude]
            <input
              name="depot"
              className="field font-mono text-xs"
              defaultValue="[77.58,12.95]"
              required
            />
          </label>
          {error && (
            <p className="text-sm text-red-800 md:col-span-2">{error}</p>
          )}
          <button className="btn-primary" disabled={busy}>
            Save delivery configuration
          </button>
        </form>
      </section>
    </div>
  );
}

function Settings({ data }: Common) {
  return <BusinessProfile user={data.user} />;
}

function Operations({
  data,
  act,
  busy,
  section,
}: Common & { section: string }) {
  const [auditQuery, setAuditQuery] = useState("");
  const [auditPage, setAuditPage] = useState(0);
  const audit = useQuery({
    queryKey: ["audit-history", data.user.id, auditQuery, auditPage],
    queryFn: () =>
      request<{ items: Audit[]; total: number }>(
        `/api/v1/audit?${new URLSearchParams({ q: auditQuery, offset: String(auditPage * 20), limit: "20" })}`,
      ),
    enabled: section !== "notifications",
    refetchInterval: 5000,
  });
  const auditRows = audit.data?.items ?? [];
  const total = audit.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / 20));
  const currentPage = auditPage;
  if (section === "notifications")
    return (
      <section className="card">
        <h3 className="font-bold">Your messages</h3>
        {data.notifications.length ? (
          data.notifications.map((n) => (
            <article
              key={n.id}
              className="flex flex-wrap items-center justify-between gap-3 border-b py-4"
            >
              <div>
                <b className="text-sm">{n.action.replaceAll("_", " ")}</b>
                <p className="mt-1 text-xs text-slate-500">
                  {new Date(n.created_at).toLocaleString()} · {n.subject}
                </p>
              </div>
              {!n.read && (
                <button
                  className="btn-secondary"
                  disabled={busy}
                  onClick={() =>
                    act(`/api/v1/notifications/${n.id}/read`).catch(() => {})
                  }
                >
                  Mark read
                </button>
              )}
            </article>
          ))
        ) : (
          <p className="mt-4 text-sm text-slate-500">
            No updates yet. Order and delivery events will appear here.
          </p>
        )}
      </section>
    );
  return (
    <div className="space-y-5">
      {["environment", "integrations"].includes(section) && (
        <section className="card">
          <h3 className="font-bold">Connected environment</h3>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {[
              [
                "Payments",
                data.payment_provider === "demo"
                  ? "Explicit offline simulation"
                  : "PayPal sandbox adapter",
              ],
              ["Persistence", "SQLAlchemy transactional store"],
              ["Clearing", "OR-Tools + independent validation"],
              ["External agent checkout", "ACP disabled pending eligibility"],
              ["Settlement", "Direct merchant capture; no pooled wallet"],
              ["AI", "Configured server-side; offline mode is labelled"],
            ].map(([a, b]) => (
              <div className="rounded-xl bg-slate-50 p-4 text-sm" key={a}>
                <b>{a}</b>
                <p className="mt-1 text-slate-500">{b}</p>
              </div>
            ))}
          </div>
        </section>
      )}
      {["users", "seller-verification"].includes(section) && (
        <>
          {section === "seller-verification" && (
            <SellerReviewQueue act={act} busy={busy} />
          )}
          <section className="card">
            <h3 className="font-bold">Accounts & permissions</h3>
            {data.people.map((p) => (
              <div
                className="flex flex-wrap items-center justify-between gap-3 border-b py-4"
                key={p.id}
              >
                <div>
                  <b>{p.name}</b>
                  <p className="text-xs text-slate-500">
                    {p.email} · {p.roles.join(", ")}
                    {p.active === false && " · ACCOUNT DISABLED"}
                  </p>
                </div>
                {p.id !== data.user.id && (
                  <button
                    className="btn-secondary"
                    disabled={busy}
                    onClick={() => {
                      const reason = window.prompt(
                        `Reason to ${p.active === false ? "reactivate" : "disable"} ${p.name}'s account (at least 5 characters):`,
                      );
                      if (reason && reason.trim().length >= 5)
                        act(`/api/v1/admin/users/${p.id}/state`, {
                          active: p.active === false,
                          reason: reason.trim(),
                        }).catch(() => {});
                    }}
                  >
                    {p.active === false ? "Reactivate" : "Disable"} {p.name}
                  </button>
                )}
                {!p.verified && (
                  <button
                    className="btn-secondary"
                    disabled={busy}
                    onClick={() =>
                      window.confirm(`Verify ${p.name}'s business?`) &&
                      act(`/api/v1/admin/users/${p.id}/verify`).catch(() => {})
                    }
                  >
                    Verify business
                  </button>
                )}
                <select
                  aria-label={`Grant role to ${p.name}`}
                  className="field !mt-0 !w-auto"
                  value=""
                  disabled={busy || p.id === data.user.id}
                  onChange={(e) => {
                    if (
                      e.target.value &&
                      window.confirm(
                        `Grant ${e.target.value} access to ${p.name}?`,
                      )
                    )
                      act(`/api/v1/admin/users/${p.id}/roles`, {
                        role: e.target.value,
                      }).catch(() => {});
                  }}
                >
                  <option value="">Grant role…</option>
                  {["RETAILER", "SELLER", "DRIVER", "ADMIN"].map((r) => (
                    <option key={r}>{r}</option>
                  ))}
                </select>
                {p.id !== data.user.id &&
                  p.roles.map((role) => (
                    <button
                      className="btn-secondary"
                      key={role}
                      disabled={busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            `Remove ${role} access from ${p.name}? Existing sessions lose this permission immediately.`,
                          )
                        )
                          act(`/api/v1/admin/users/${p.id}/roles/revoke`, {
                            role,
                          }).catch(() => {});
                      }}
                    >
                      Remove {role} from {p.name}
                    </button>
                  ))}
              </div>
            ))}
          </section>
        </>
      )}
      <section className="card">
        <h3 className="font-bold">Activity & audit trail</h3>
        {audit.error && (
          <p role="alert" className="mt-3 text-red-800">
            {audit.error.message}
          </p>
        )}
        <p className="mt-2 text-xs text-slate-500">
          Search your accessible server audit history, including older events.
        </p>
        <input
          className="field mt-4"
          aria-label="Search audit events"
          placeholder="Search action, actor, subject or date"
          value={auditQuery}
          onChange={(e) => {
            setAuditQuery(e.target.value);
            setAuditPage(0);
          }}
        />
        {auditRows.length ? (
          auditRows.map((a) => (
            <div
              className="flex flex-wrap justify-between gap-2 border-b py-3 text-sm"
              key={a.id}
            >
              <div>
                <b>{a.action.replaceAll("_", " ")}</b>
                <p className="mt-1 font-mono text-[10px] text-slate-500">
                  {a.subject} · Actor: {a.actor}
                </p>
              </div>
              <span className="text-xs text-slate-500">
                {new Date(a.at).toLocaleString()}
              </span>
            </div>
          ))
        ) : (
          <p className="mt-4 text-sm text-slate-500">
            {audit.isLoading
              ? "Loading audit history…"
              : auditQuery
                ? "No matching activity."
                : "No account activity yet."}
          </p>
        )}
        <div className="mt-4 flex items-center justify-between gap-3 text-sm">
          <button
            className="btn-secondary"
            disabled={currentPage === 0 || audit.isFetching}
            onClick={() => setAuditPage(currentPage - 1)}
          >
            Previous events
          </button>
          <span>
            {total} events · Page {currentPage + 1} of {pageCount}
          </span>
          <button
            className="btn-secondary"
            disabled={currentPage + 1 >= pageCount || audit.isFetching}
            onClick={() => setAuditPage(currentPage + 1)}
          >
            Next events
          </button>
        </div>
      </section>
    </div>
  );
}

function DriverRoute({ data }: { data: Workspace }) {
  return (
    <>
      {data.pools
        .filter(
          (p) => p.driver_id === data.user.id && p.status === "DISPATCHED",
        )
        .map((p) => (
          <section key={p.id} className="card">
            <h3 className="font-bold">
              Ordered delivery stops · {p.dispatch_date}
            </h3>
            <p className="mt-2 text-xs text-slate-500">
              OR-Tools stop order uses geographic distance. Open navigation for
              road directions.
            </p>
            <ol className="mt-4 space-y-3">
              {p.route?.map((rid, index) => {
                const o = data.orders.find(
                  (o) => o.request_id === rid && o.pool_id === p.id,
                );
                const buyer = data.people.find((b) => b.id === o?.buyer_id);
                return (
                  <li
                    key={rid}
                    className="flex flex-wrap justify-between gap-2 rounded-xl bg-slate-50 p-3 text-sm"
                  >
                    <span>
                      <b>
                        {index + 1}. {buyer?.name ?? o?.buyer_id}
                      </b>{" "}
                      · {o?.quantity} units{" "}
                      {o?.pod ? "· evidence recorded" : "· awaiting delivery"}
                    </span>
                    {buyer && (
                      <a
                        className="font-bold text-blue-700"
                        href={`https://www.google.com/maps/dir/?api=1&destination=${buyer.location[1]},${buyer.location[0]}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open navigation ↗
                      </a>
                    )}
                  </li>
                );
              })}
            </ol>
          </section>
        ))}
    </>
  );
}

function ExceptionForm({
  order,
  act,
  busy,
}: {
  order: Order;
  act: Act;
  busy: boolean;
}) {
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (
      !window.confirm(
        "Apply this resolution and preserve the delivery evidence?",
      )
    )
      return;
    try {
      await act(`/api/v1/orders/${order.id}/resolve-exception`, {
        action: f.get("action"),
        reason: f.get("reason"),
        returned_quantity: Number(f.get("returned")),
        replacement_quantity: Number(f.get("replacement")),
      });
    } catch {}
  }
  return (
    <form
      onSubmit={submit}
      className="mt-4 grid gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 md:grid-cols-2"
    >
      <label className="label">
        Exception resolution
        <select name="action" className="field">
          <option value="REDELIVER">Arrange another delivery attempt</option>
          <option value="VOID_AND_CLOSE">
            Void authorization & close order
          </option>
        </select>
      </label>
      <label className="label">
        Resolution reason
        <input name="reason" className="field" minLength={3} required />
      </label>
      <label className="label">
        Saleable units returned to stock
        <input
          name="returned"
          className="field"
          type="number"
          min="0"
          max={order.quantity}
          defaultValue="0"
          required
        />
      </label>
      <label className="label">
        Additional replacement units dispatched
        <input
          name="replacement"
          className="field"
          type="number"
          min="0"
          max={order.quantity}
          defaultValue="0"
          required
        />
      </label>
      <p className="text-xs leading-5 text-amber-900 md:col-span-2">
        Record actual stock movements. A redelivery reports cumulative good
        units received, capped at the original quantity. The agreed payment
        cannot increase.
      </p>
      <button className="btn-secondary md:col-span-2" disabled={busy}>
        Apply exception resolution
      </button>
    </form>
  );
}
