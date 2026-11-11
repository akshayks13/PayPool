"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/commerce-workspace";
import { ZoneMap } from "@/components/zone-map";
import { money, type Product, type Zone } from "@/lib/commerce";
import { request } from "@/lib/http";
import type { Role } from "@/lib/roles";
import type { FeatureProps, Features, Offer, Vehicle } from "@/lib/features";

type Props = FeatureProps & { role: Role; section: string };
export function PlatformFeatures(props: Props) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["features", props.data.user.id],
    queryFn: () => request<Features>("/api/v1/features"),
    refetchInterval: 5000,
  });
  const act: FeatureProps["act"] = async (...args) => {
    const value = await props.act(...args);
    await client.invalidateQueries({ queryKey: ["features"] });
    await client.invalidateQueries({ queryKey: ["system-health"] });
    return value;
  };
  if (query.error)
    return (
      <p role="alert" className="card text-red-800">
        {query.error.message}
      </p>
    );
  if (!query.data)
    return <p className="card text-slate-500">Loading current operations…</p>;
  const common = { ...props, act, features: query.data };
  if (props.section === "product-feed") return <ProductFeed {...common} />;
  if (props.section === "offers") return <Negotiations {...common} />;
  if (props.section === "standing-orders")
    return <StandingOrders {...common} />;
  if (props.section === "fleet") return <Fleet {...common} />;
  if (props.section === "inventory") return <Stock {...common} />;
  if (props.section === "service-areas") return <Areas {...common} />;
  if (props.section === "agent-access") return <AgentAccess {...common} />;
  return <SystemOperations {...common} />;
}
type FullProps = Props & { features: Features };

function Negotiations({ data, features, act, busy, role }: FullProps) {
  const eligible = data.requests.filter(
    (r) =>
      r.status === "ACTIVE" &&
      ["ACCUMULATING", "FAILED"].includes(
        data.pools.find((p) => p.id === r.pool_id)?.status ?? "",
      ),
  );
  const [selected, setSelected] = useState("");
  const [counter, setCounter] = useState<Offer | null>(null);
  const [price, setPrice] = useState("1.50");
  const [result, setResult] = useState("");
  const [operation, setOperation] = useState("");
  const buying = eligible.find((r) => r.id === selected) ?? eligible[0];
  useEffect(() => {
    setOperation(crypto.randomUUID());
  }, [counter, selected]);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!buying) return;
    const f = new FormData(e.currentTarget);
    const terms = {
      product_id: f.get("product"),
      quantity_min: Number(f.get("min")),
      quantity_max: Number(f.get("max")),
      unit_price_minor: Math.round(Number(price) * 100),
      expires_in_hours: Number(f.get("expiry")),
      note: String(f.get("note") ?? ""),
    };
    try {
      await act(
        counter ? `/api/v1/offers/${counter.id}/counter` : "/api/v1/offers",
        counter
          ? { ...terms, version: counter.version }
          : { ...terms, request_id: buying.id },
        { "Idempotency-Key": operation },
      );
      setCounter(null);
      setOperation(crypto.randomUUID());
    } catch {}
  }
  const product = data.products.find((p) => p.id === buying?.product_id);
  return (
    <div className="space-y-5">
      <section className="rounded-2xl bg-ink p-6 text-white">
        <h2 className="text-xl font-bold">
          Agree on the offer. Approve the final order.
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-blue-100">
          Buyer and supplier exchange bounded terms here. Shared freight is
          calculated at clearing; an accepted offer never authorizes payment.
        </p>
      </section>
      {!!eligible.length && (
        <section className="card">
          <h3 className="font-bold">
            {counter
              ? `Counter offer · version ${counter.version}`
              : "Propose commercial terms"}
          </h3>
          <label className="label mt-4 block">
            Buying request
            <select
              className="field"
              value={buying?.id ?? ""}
              onChange={(e) => {
                setSelected(e.target.value);
                setCounter(null);
              }}
            >
              {eligible.map((r) => (
                <option key={r.id} value={r.id}>
                  {data.products.find((p) => p.id === r.product_id)?.title} ·{" "}
                  {r.buyer_id} · {r.dispatch_date}
                </option>
              ))}
            </select>
          </label>
          {role === "RETAILER" && buying && (
            <button
              className="btn-secondary mt-3"
              disabled={busy}
              onClick={async () => {
                try {
                  const r = (await act(
                    `/api/v1/procurement/requests/${buying.id}/negotiate`,
                  )) as {
                    status: string;
                    proposal: { unit_price_minor: number };
                  };
                  setPrice((r.proposal.unit_price_minor / 100).toFixed(2));
                  setResult(
                    r.status === "PROPOSED"
                      ? "The supplier's current earned tier is ready for your proposal. Freight remains subject to clearing."
                      : "More demand or an explicit supplier counter is needed within your limit.",
                  );
                } catch {}
              }}
            >
              Ask buyer & supplier agents
            </button>
          )}
          {result && (
            <p
              role="status"
              className="mt-3 rounded-xl bg-blue-50 p-3 text-sm text-blue-900"
            >
              {result}
            </p>
          )}
          <form
            key={`${buying?.id}:${counter?.id ?? "new"}:${counter?.version ?? 0}`}
            onSubmit={submit}
            className="mt-4 grid gap-4 md:grid-cols-3"
          >
            <label className="label">
              Approved product
              <select
                className="field"
                name="product"
                defaultValue={counter?.terms.product_id ?? buying?.product_id}
              >
                {data.products
                  .filter(
                    (p) =>
                      p.id === buying?.product_id ||
                      buying?.substitute_product_ids?.includes(p.id),
                  )
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.title}
                    </option>
                  ))}
              </select>
            </label>
            <label className="label">
              Offer minimum
              <input
                name="min"
                className="field"
                type="number"
                min={buying?.quantity_min}
                max={buying?.quantity_max}
                defaultValue={
                  counter?.terms.quantity_min ?? buying?.quantity_min
                }
                required
              />
            </label>
            <label className="label">
              Offer maximum
              <input
                name="max"
                className="field"
                type="number"
                min={buying?.quantity_min}
                max={buying?.quantity_max}
                defaultValue={
                  counter?.terms.quantity_max ?? buying?.quantity_max
                }
                required
              />
            </label>
            <label className="label">
              Unit offer ({product?.currency} / {product?.unit})
              <input
                className="field"
                type="number"
                step="0.01"
                min="0.01"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                required
              />
            </label>
            <label className="label">
              Valid for (hours)
              <input
                className="field"
                name="expiry"
                type="number"
                min="1"
                max="168"
                defaultValue="24"
                required
              />
            </label>
            <label className="label">
              Commercial note
              <input
                className="field"
                name="note"
                maxLength={1000}
                defaultValue={counter?.terms.note ?? ""}
              />
            </label>
            <div className="flex gap-2 md:col-span-3">
              <button className="btn-primary" disabled={busy}>
                Send {counter ? "counteroffer" : "proposal"}
              </button>
              {counter && (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setCounter(null)}
                >
                  Cancel counter
                </button>
              )}
            </div>
          </form>
        </section>
      )}
      {!features.offers.length && (
        <div className="card text-sm text-slate-500">
          No commercial offers yet.{" "}
          {role === "RETAILER" ? (
            <Link href="/retailer/catalog" className="text-blue-700 underline">
              Create a buying request
            </Link>
          ) : (
            "Buyers first create a request from your catalog."
          )}
        </div>
      )}
      {features.offers
        .slice()
        .reverse()
        .map((o) => (
          <article className="card" key={o.id}>
            <div className="flex flex-wrap justify-between gap-3">
              <div>
                <h3 className="font-bold">
                  {
                    data.products.find((p) => p.id === o.terms.product_id)
                      ?.title
                  }
                </h3>
                <p className="mt-2 text-sm text-slate-500">
                  {o.terms.quantity_min}–{o.terms.quantity_max} {o.unit} ·{" "}
                  {money(o.terms.unit_price_minor, o.currency)} / {o.unit}{" "}
                  before shared freight · version {o.version}
                </p>
              </div>
              <Badge value={o.status} />
            </div>
            <p className="mt-3 text-sm">{o.terms.note}</p>
            <p className="mt-2 text-xs text-slate-500">
              Expires {new Date(o.expires_at).toLocaleString()} · proposed by{" "}
              {data.people.find((u) => u.id === o.actor)?.name ?? o.actor}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {["SUBMITTED", "COUNTERED"].includes(o.status) &&
                new Date(o.expires_at).getTime() > Date.now() && (
                  <>
                    <button
                      className="btn-secondary"
                      disabled={
                        busy || !eligible.some((r) => r.id === o.request_id)
                      }
                      onClick={() => {
                        setSelected(o.request_id);
                        setCounter(o);
                        setPrice((o.terms.unit_price_minor / 100).toFixed(2));
                        window.scrollTo({ top: 0, behavior: "smooth" });
                      }}
                    >
                      Propose counter
                    </button>
                    {o.actor !== data.user.id && (
                      <button
                        className="btn-primary"
                        disabled={busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              "Accept these base terms? Final freight and order approval follow separately.",
                            )
                          )
                            act(`/api/v1/offers/${o.id}/accept`, {
                              version: o.version,
                            }).catch(() => {});
                        }}
                      >
                        Accept offer · version {o.version}
                      </button>
                    )}
                  </>
                )}
              {o.status === "ACCEPTED" && (
                <Link
                  className="btn-primary"
                  href={`/${role.toLowerCase()}/pools`}
                >
                  Review final shared order
                </Link>
              )}
            </div>
          </article>
        ))}
    </div>
  );
}

function StandingOrders({ data, features, act, busy }: FullProps) {
  const [product, setProduct] = useState(data.products[0]?.id ?? "");
  const item = data.products.find((p) => p.id === product);
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await act("/api/v1/standing-orders", {
        name: f.get("name"),
        repeat_days: Number(f.get("repeat")),
        lookahead_days: Number(f.get("lookahead")),
        end_date: f.get("end") || null,
        request: {
          product_id: product,
          zone_id: f.get("zone"),
          dispatch_date: f.get("date"),
          quantity_min: Number(f.get("min")),
          quantity_max: Number(f.get("max")),
          ceiling_minor: Math.round(Number(f.get("ceiling")) * 100),
        },
      });
    } catch {}
  }
  return (
    <div className="space-y-5">
      <section className="card">
        <h2 className="text-xl font-bold">Recurring buying instructions</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          Schedule recurring requests within your limits. Each occurrence still
          needs final order approval and individual payment authorization.
        </p>
        <form onSubmit={submit} className="mt-5 grid gap-4 md:grid-cols-3">
          <label className="label">
            Instruction name
            <input
              name="name"
              className="field"
              defaultValue="Weekly stock"
              minLength={2}
              required
            />
          </label>
          <label className="label">
            Product
            <select
              className="field"
              value={product}
              onChange={(e) => setProduct(e.target.value)}
            >
              {data.products
                .filter((p) => p.active !== false)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title}
                  </option>
                ))}
            </select>
          </label>
          <label className="label">
            Delivery area
            <select className="field" name="zone">
              {data.zones
                .filter(
                  (z) =>
                    z.seller_id === item?.seller_id &&
                    z.currency === item?.currency,
                )
                .map((z) => (
                  <option value={z.id} key={z.id}>
                    {z.name}
                  </option>
                ))}
            </select>
          </label>
          {[
            ["min", "Minimum quantity", "30"],
            ["max", "Maximum quantity", "30"],
            [
              "ceiling",
              `Delivered ceiling (${item?.currency} / ${item?.unit})`,
              "1.70",
            ],
            ["repeat", "Repeat every (days)", "7"],
            ["lookahead", "Create request this many days ahead", "7"],
          ].map(([name, label, value]) => (
            <label className="label" key={name}>
              {label}
              <input
                name={name}
                className="field"
                type="number"
                step={name === "ceiling" ? "0.01" : "1"}
                min={name === "lookahead" ? 0 : 1}
                defaultValue={value}
                required
              />
            </label>
          ))}
          <label className="label">
            First delivery date
            <input
              name="date"
              type="date"
              className="field"
              defaultValue={tomorrow}
              required
            />
          </label>
          <label className="label">
            End date (optional)
            <input name="end" type="date" className="field" />
          </label>
          <button
            className="btn-primary md:col-span-3"
            disabled={busy || !item}
          >
            Save recurring instruction
          </button>
        </form>
      </section>
      {features.standing_orders.map((s) => (
        <article className="card" key={s.id}>
          <div className="flex justify-between gap-3">
            <h3 className="font-bold">{s.name}</h3>
            <Badge value={s.active ? "ACTIVE" : (s.status ?? "PAUSED")} />
          </div>
          <p className="mt-3 text-sm text-slate-500">
            Next dispatch {s.next_dispatch_date} · repeats every {s.repeat_days}{" "}
            days · {s.request.quantity_min}–{s.request.quantity_max} units
          </p>
          {s.last_error && (
            <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
              {s.last_error}
            </p>
          )}
          <button
            className="btn-secondary mt-4"
            disabled={busy}
            onClick={() =>
              act(`/api/v1/standing-orders/${s.id}/state`, {
                active: !s.active,
              }).catch(() => {})
            }
          >
            {s.active ? "Pause instruction" : "Resume instruction"}
          </button>
        </article>
      ))}
    </div>
  );
}

function Fleet({ features, act, busy }: FullProps) {
  const client = useQueryClient();
  const [editing, setEditing] = useState<Vehicle | null>(null);
  const [error, setError] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = {
      name: f.get("name"),
      registration: f.get("registration"),
      max_weight_grams: Math.round(Number(f.get("weight")) * 1000),
      max_volume_cm3: Number(f.get("volume")),
      active: f.get("active") === "on",
    };
    try {
      if (editing) {
        await request(`/api/v1/seller/vehicles/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
        await client.invalidateQueries({ queryKey: ["features"] });
      } else await act("/api/v1/seller/vehicles", body);
      setEditing(null);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
  }
  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        {features.vehicles.map((v) => (
          <article className="card" key={v.id}>
            <div className="flex justify-between">
              <h3 className="font-bold">{v.name}</h3>
              <Badge value={v.active ? "ACTIVE" : "INACTIVE"} />
            </div>
            <p className="mt-2 text-sm text-slate-500">
              {v.registration} · {v.max_weight_grams / 1000} kg ·{" "}
              {v.max_volume_cm3 / 1000000} m³
            </p>
            <button
              className="btn-secondary mt-4"
              onClick={() => setEditing(v)}
            >
              Edit vehicle
            </button>
          </article>
        ))}
      </div>
      <section className="card">
        <h3 className="font-bold">
          {editing ? "Edit fleet vehicle" : "Add fleet vehicle"}
        </h3>
        <form
          key={editing?.id ?? "new"}
          onSubmit={submit}
          className="mt-4 grid gap-4 md:grid-cols-2"
        >
          {[
            ["name", "Vehicle name", editing?.name ?? "Delivery van"],
            ["registration", "Registration", editing?.registration ?? ""],
            [
              "weight",
              "Maximum load (kg)",
              String((editing?.max_weight_grams ?? 200000) / 1000),
            ],
            [
              "volume",
              "Packed capacity (cm³)",
              String(editing?.max_volume_cm3 ?? 400000),
            ],
          ].map(([name, label, value]) => (
            <label className="label" key={name}>
              {label}
              <input
                className="field"
                name={name}
                defaultValue={value}
                required
              />
            </label>
          ))}
          <label className="flex gap-2 text-sm">
            <input
              type="checkbox"
              name="active"
              defaultChecked={editing?.active ?? true}
            />
            Available for assignment
          </label>
          {error && (
            <p role="alert" className="text-sm text-red-800">
              {error}
            </p>
          )}
          <div className="flex gap-2 md:col-span-2">
            <button className="btn-primary" disabled={busy}>
              Save vehicle
            </button>
            {editing && (
              <button
                className="btn-secondary"
                type="button"
                onClick={() => setEditing(null)}
              >
                Cancel edit
              </button>
            )}
          </div>
        </form>
      </section>
    </div>
  );
}

function Stock({ data, features, act, busy }: FullProps) {
  async function submit(e: FormEvent<HTMLFormElement>, product: Product) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await act("/api/v1/seller/inventory", {
        product_id: product.id,
        delta: Number(f.get("delta")),
        expected_stock: product.stock,
        reason: f.get("reason"),
      });
    } catch {}
  }
  return (
    <div className="space-y-5">
      {data.products
        .filter((p) => p.seller_id === data.user.id)
        .map((p) => (
          <article className="card" key={p.id}>
            <div className="flex justify-between">
              <div>
                <h3 className="font-bold">{p.title}</h3>
                <p className="mt-2 text-sm text-slate-500">
                  On hand {p.stock} · available {p.available_stock} {p.unit} ·
                  reserved {p.stock - p.available_stock}
                </p>
              </div>
              <Badge value={p.active === false ? "ARCHIVED" : "ACTIVE"} />
            </div>
            <form
              onSubmit={(e) => submit(e, p)}
              className="mt-4 flex flex-wrap items-end gap-3"
            >
              <label className="label">
                Stock adjustment
                <input
                  name="delta"
                  type="number"
                  className="field"
                  defaultValue="0"
                  required
                />
              </label>
              <label className="label flex-1">
                Reason
                <input
                  name="reason"
                  className="field"
                  minLength={3}
                  placeholder="Restock, count correction or write-off"
                  required
                />
              </label>
              <button className="btn-primary" disabled={busy}>
                Record adjustment
              </button>
              <button
                className="btn-secondary"
                type="button"
                disabled={busy}
                onClick={() => {
                  if (
                    window.confirm(
                      `${p.active === false ? "Restore" : "Archive"} this catalog product?`,
                    )
                  )
                    act(`/api/v1/seller/products/${p.id}/archive`, {
                      active: p.active === false,
                    }).catch(() => {});
                }}
              >
                {p.active === false ? "Restore product" : "Archive product"}
              </button>
            </form>
          </article>
        ))}
      <section className="card">
        <h3 className="font-bold">Stock movement history</h3>
        {features.stock_movements
          .slice()
          .reverse()
          .map((m) => (
            <p className="border-b py-3 text-sm" key={m.id}>
              <b>
                {m.delta > 0 ? "+" : ""}
                {m.delta}
              </b>{" "}
              · {data.products.find((p) => p.id === m.product_id)?.title} ·
              balance {m.balance}
              <span className="mt-1 block text-xs text-slate-500">
                {m.reason} · {new Date(m.at).toLocaleString()}
              </span>
            </p>
          ))}
      </section>
    </div>
  );
}

function Areas({ data, act, busy }: FullProps) {
  const client = useQueryClient();
  const [editing, setEditing] = useState<Zone | null>(null);
  const [polygon, setPolygon] = useState(
    "[[77.5,12.9],[77.7,12.9],[77.7,13.05],[77.5,13.05]]",
  );
  const [error, setError] = useState("");
  let coordinates: [number, number][] = [];
  try {
    const p = JSON.parse(polygon);
    if (
      Array.isArray(p) &&
      p.every(
        (v) => Array.isArray(v) && v.length === 2 && v.every(Number.isFinite),
      )
    )
      coordinates = p;
  } catch {}
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      const body = {
        name: f.get("name"),
        currency: f.get("currency"),
        polygon: JSON.parse(polygon),
        depot: JSON.parse(String(f.get("depot"))),
        base_freight_minor: Math.round(Number(f.get("base")) * 100),
        stop_fee_minor: Math.round(Number(f.get("stop")) * 100),
        min_weight_grams: Math.round(Number(f.get("min")) * 1000),
        max_weight_grams: Math.round(Number(f.get("max")) * 1000),
        max_volume_cm3: Number(f.get("volume")),
        freight_weight_percent: Number(f.get("alpha")),
        timezone: f.get("timezone"),
        dispatch_time: f.get("time"),
        delivery_window: f.get("window"),
        cutoff_hours_before: Number(f.get("cutoff")),
        weekdays: String(f.get("days")).split(",").map(Number),
        auto_clear_at_cutoff: f.get("auto") === "on",
        recipient_confirmation_required: f.get("confirmation") === "on",
        active: f.get("active") === "on",
      };
      if (editing) {
        await request(`/api/v1/seller/zones/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
        await client.invalidateQueries({ queryKey: ["workspace"] });
      } else await act("/api/v1/seller/zones", body);
      setEditing(null);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invalid delivery area");
    }
  }
  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        {data.zones
          .filter((z) => z.seller_id === data.user.id)
          .map((z) => (
            <article className="card" key={z.id}>
              <h3 className="font-bold">{z.name}</h3>
              <p className="mt-2 text-sm text-slate-500">
                {money(z.base_freight_minor, z.currency)} base +{" "}
                {money(z.stop_fee_minor, z.currency)} / stop ·{" "}
                {z.min_weight_grams / 1000}–{z.max_weight_grams / 1000} kg
              </p>
              <p className="mt-2 text-xs text-slate-500">
                {z.delivery_window ?? "09:00–18:00"} · cutoff{" "}
                {z.cutoff_hours_before ?? 0}h before dispatch ·{" "}
                {z.freight_weight_percent ?? 50}% weight /{" "}
                {100 - (z.freight_weight_percent ?? 50)}% volume
              </p>
              <button
                className="btn-secondary mt-4"
                onClick={() => {
                  setEditing(z);
                  setPolygon(JSON.stringify(z.polygon));
                }}
              >
                Edit boundary & schedule
              </button>
            </article>
          ))}
      </div>
      <section className="card">
        <h3 className="font-bold">
          {editing ? "Edit delivery boundary" : "Create delivery area"}
        </h3>
        <div className="mt-4">
          <ZoneMap
            coordinates={coordinates}
            onChange={(points) => setPolygon(JSON.stringify(points))}
          />
        </div>
        <form
          key={editing?.id ?? "new"}
          onSubmit={submit}
          className="mt-5 grid gap-4 md:grid-cols-3"
        >
          {[
            ["name", "Area name", editing?.name ?? "New delivery area"],
            ["currency", "Currency", editing?.currency ?? "USD"],
            [
              "base",
              "Base route fee",
              String((editing?.base_freight_minor ?? 600) / 100),
            ],
            [
              "stop",
              "Per-stop fee",
              String((editing?.stop_fee_minor ?? 100) / 100),
            ],
            [
              "min",
              "Minimum dispatch weight (kg)",
              String((editing?.min_weight_grams ?? 50000) / 1000),
            ],
            [
              "max",
              "Maximum load (kg)",
              String((editing?.max_weight_grams ?? 200000) / 1000),
            ],
            [
              "volume",
              "Vehicle capacity (cm³)",
              String(editing?.max_volume_cm3 ?? 400000),
            ],
            [
              "alpha",
              "Freight weight percentage",
              String(editing?.freight_weight_percent ?? 50),
            ],
            ["timezone", "Timezone", editing?.timezone ?? "Asia/Kolkata"],
            ["time", "Dispatch time", editing?.dispatch_time ?? "09:00"],
            [
              "window",
              "Delivery window",
              editing?.delivery_window ?? "09:00–18:00",
            ],
            [
              "cutoff",
              "Cutoff hours before dispatch",
              String(editing?.cutoff_hours_before ?? 0),
            ],
            [
              "days",
              "Run weekdays (0 Monday … 6 Sunday)",
              (editing?.weekdays ?? [0, 1, 2, 3, 4, 5, 6]).join(","),
            ],
            [
              "depot",
              "Depot [longitude, latitude]",
              JSON.stringify(editing?.depot ?? [77.58, 12.95]),
            ],
          ].map(([name, label, value]) => (
            <label className="label" key={name}>
              {label}
              <input
                className="field"
                name={name}
                defaultValue={value}
                required
              />
            </label>
          ))}
          <label className="label md:col-span-3">
            Boundary coordinates [longitude, latitude]
            <textarea
              className="field font-mono text-xs"
              value={polygon}
              onChange={(e) => setPolygon(e.target.value)}
              required
            />
          </label>
          <label className="flex gap-2 text-sm">
            <input
              name="auto"
              type="checkbox"
              defaultChecked={editing?.auto_clear_at_cutoff ?? true}
            />
            Clear automatically at cutoff
          </label>
          <label className="flex gap-2 text-sm">
            <input
              name="confirmation"
              type="checkbox"
              defaultChecked={editing?.recipient_confirmation_required ?? true}
            />
            Buyer confirms receipt before capture
          </label>
          <label className="flex gap-2 text-sm">
            <input
              name="active"
              type="checkbox"
              defaultChecked={editing?.active ?? true}
            />
            Area is active
          </label>
          {error && (
            <p role="alert" className="text-sm text-red-800 md:col-span-3">
              {error}
            </p>
          )}
          <div className="flex gap-2 md:col-span-3">
            <button className="btn-primary" disabled={busy}>
              Save delivery area
            </button>
            {editing && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setEditing(null)}
              >
                Cancel edit
              </button>
            )}
          </div>
        </form>
      </section>
    </div>
  );
}

function AgentAccess({ features, act, busy }: FullProps) {
  const [token, setToken] = useState("");
  return (
    <div className="space-y-5">
      <section className="card">
        <h2 className="text-xl font-bold">External agent access</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          Create temporary, revocable access to your approved quotes and
          checkout continuation. Agents cannot approve purchases or authorize
          payment. External payment processing remains disabled pending merchant
          access.
        </p>
        <form
          className="mt-4 flex flex-wrap items-end gap-3"
          onSubmit={async (e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            try {
              const result = (await act("/api/v1/me/agent-access", {
                name: f.get("name"),
                expires_in_hours: Number(f.get("hours")),
              })) as { token: string };
              setToken(result.token);
            } catch {}
          }}
        >
          <label className="label flex-1">
            Agent label
            <input
              className="field"
              name="name"
              minLength={2}
              defaultValue="My procurement assistant"
              required
            />
          </label>
          <label className="label">
            Hours until expiry
            <input
              className="field"
              name="hours"
              type="number"
              min="1"
              max="168"
              defaultValue="8"
              required
            />
          </label>
          <button className="btn-primary" disabled={busy}>
            Create restricted access
          </button>
        </form>
        {token && (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
            <p className="text-sm font-bold">
              Shown once. Keep this access token private.
            </p>
            <code className="mt-2 block break-all text-xs">{token}</code>
            <button className="btn-secondary mt-3" onClick={() => setToken("")}>
              Hide token
            </button>
          </div>
        )}
      </section>
      {features.agent_access?.map((a) => (
        <article
          className="card flex flex-wrap items-center justify-between gap-3"
          key={a.client_id}
        >
          <div>
            <b>{a.name}</b>
            <p className="mt-1 text-xs text-slate-500">
              Expires {new Date(a.expires_at).toLocaleString()}
            </p>
          </div>
          {a.active ? (
            <button
              className="btn-secondary"
              disabled={busy}
              onClick={() =>
                act(`/api/v1/me/agent-access/${a.client_id}/revoke`).catch(
                  () => {},
                )
              }
            >
              Revoke access
            </button>
          ) : (
            <Badge value="REVOKED" />
          )}
        </article>
      ))}
    </div>
  );
}

function SystemOperations({ features, act, busy }: FullProps) {
  const query = useQuery({
    queryKey: ["system-health"],
    queryFn: () =>
      request<{
        worker: { last_tick: string } | null;
        queue: Record<string, number>;
        payment_states: Record<string, number>;
        capabilities: Record<string, boolean>;
        ledger: {
          id: string;
          action: string;
          payment_status: string;
          currency: string;
          total_minor: number;
          at: string;
        }[];
      }>("/api/v1/admin/operations"),
    refetchInterval: 5000,
  });
  if (!query.data)
    return (
      <p className="card">
        {query.error?.message ?? "Loading operational health…"}
      </p>
    );
  const data = query.data;
  return (
    <div className="space-y-5">
      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-bold">Worker & durable events</h3>
            <p className="mt-2 text-sm text-slate-500">
              Last heartbeat:{" "}
              {data.worker
                ? new Date(data.worker.last_tick).toLocaleString()
                : "No worker heartbeat yet"}
            </p>
          </div>
          <button
            className="btn-primary"
            disabled={busy}
            onClick={() => act("/api/v1/admin/worker/tick").catch(() => {})}
          >
            Run pending jobs
          </button>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          {Object.entries(data.queue).map(([state, count]) => (
            <div className="rounded-xl bg-slate-50 p-4" key={state}>
              <p className="text-xs text-slate-500">
                {state.replaceAll("_", " ")}
              </p>
              <b className="mt-2 block text-2xl">{count}</b>
            </div>
          ))}
        </div>
      </section>
      <section className="card">
        <h3 className="font-bold">Integration configuration</h3>
        <p className="mt-2 text-xs text-slate-500">
          Configuration flags do not certify external account eligibility or a
          successful live transaction.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(data.capabilities).map(([name, enabled]) => (
            <div className="rounded-xl bg-slate-50 p-4 text-sm" key={name}>
              <b>{name.replaceAll("_", " ")}</b>
              <p className="mt-1 text-slate-500">
                {enabled ? "Configured / enabled" : "Disabled / not configured"}
              </p>
            </div>
          ))}
        </div>
      </section>
      <section className="card">
        <h3 className="font-bold">Failed or pending events</h3>
        {features.jobs
          .filter((j) => j.status !== "DELIVERED")
          .map((j) => (
            <div
              className="flex flex-wrap items-center justify-between gap-3 border-b py-3 text-sm"
              key={j.id}
            >
              <div>
                <b>{j.event_type}</b>
                <p className="mt-1 text-xs text-slate-500">
                  {j.status} · {j.attempts} attempts ·{" "}
                  {j.error ?? "Awaiting processing"}
                </p>
              </div>
              {["RETRY", "DEAD_LETTER"].includes(j.status) && (
                <button
                  className="btn-secondary"
                  disabled={busy}
                  onClick={() =>
                    act(`/api/v1/admin/jobs/${j.id}/retry`).catch(() => {})
                  }
                >
                  Retry event
                </button>
              )}
            </div>
          ))}
      </section>
      <section className="card">
        <h3 className="font-bold">Payment activity ledger</h3>
        {data.ledger.map((e) => (
          <div
            className="flex flex-wrap justify-between gap-2 border-b py-3 text-sm"
            key={e.id}
          >
            <div>
              <b>{e.action.replaceAll("_", " ")}</b>
              <p className="mt-1 text-xs text-slate-500">
                {new Date(e.at).toLocaleString()}
              </p>
            </div>
            <span>
              {money(e.total_minor, e.currency)} · {e.payment_status}
            </span>
          </div>
        ))}
      </section>
    </div>
  );
}

function ProductFeed({ act, busy }: FullProps) {
  const query = useQuery({
    queryKey: ["feed-preview"],
    queryFn: () =>
      request<{
        products: Record<string, unknown>[];
        rejected: { id: string; title: string; missing_fields: string[] }[];
        note: string;
      }>("/api/v1/seller/product-feed"),
  });
  return (
    <section className="card">
      <h2 className="text-xl font-bold">Prepare external product discovery</h2>
      <p className="mt-3 text-sm leading-6 text-slate-500">
        Export your real catalog as JSONL for a separately configured commerce
        integration. Public discovery uses the base unit price; pooled discounts
        and final freight require an approved group quote. Nothing is published
        automatically.
      </p>
      {query.data ? (
        <>
          <p className="mt-4 rounded-xl bg-blue-50 p-4 text-sm text-blue-900">
            {query.data.products.length} ready rows ·{" "}
            {query.data.rejected.length} need merchant details. External
            checkout is disabled.
          </p>
          {query.data.rejected.map((p) => (
            <div className="border-b py-4 text-sm" key={p.id}>
              <b>{p.title}</b>
              <p className="mt-1 text-xs text-amber-800">
                Add {p.missing_fields.join(", ").replaceAll("_", " ")} in the
                product editor.
              </p>
            </div>
          ))}
          <button
            className="btn-primary mt-5"
            disabled={busy || !query.data.products.length}
            onClick={async () => {
              try {
                const report = (await act(
                  "/api/v1/seller/product-feed/preview",
                )) as { products: Record<string, unknown>[] };
                const url = URL.createObjectURL(
                  new Blob(
                    [
                      report.products.map((p) => JSON.stringify(p)).join("\n") +
                        "\n",
                    ],
                    { type: "application/x-ndjson" },
                  ),
                );
                const a = document.createElement("a");
                a.href = url;
                a.download = "paypool-product-feed.jsonl";
                a.click();
                URL.revokeObjectURL(url);
              } catch {}
            }}
          >
            Validate & download prepared rows
          </button>
        </>
      ) : (
        <p className="mt-4 text-sm">
          {query.error?.message ?? "Checking current catalog details…"}
        </p>
      )}
    </section>
  );
}
