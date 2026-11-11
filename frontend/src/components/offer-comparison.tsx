"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { money, type Workspace } from "@/lib/commerce";
import type { Offer } from "@/lib/features";
import { request } from "@/lib/http";

export function OfferComparison({
  data,
  offers,
}: {
  data: Workspace;
  offers: Offer[];
}) {
  const [filter, setFilter] = useState("");
  const [status, setStatus] = useState("");
  const [buying, setBuying] = useState("");
  const [sort, setSort] = useState("expiry");
  const [history, setHistory] = useState("");
  const revisions = useQuery({
    queryKey: [
      "offer-revisions",
      data.user.id,
      history,
      offers.find((o) => o.id === history)?.version,
      offers.find((o) => o.id === history)?.status,
    ],
    queryFn: () =>
      request<Offer & { revisions: Offer[] }>(
        `/api/v1/offers/${encodeURIComponent(history)}`,
      ),
    enabled: Boolean(history),
  });
  const product = (o: Offer) =>
    data.products.find((p) => p.id === o.terms.product_id);
  const rows = offers
    .filter(
      (o) =>
        (!status || o.status === status) &&
        (!buying || o.request_id === buying) &&
        `${product(o)?.title ?? o.terms.product_id} ${o.id} ${o.request_id} ${o.terms.note}`
          .toLowerCase()
          .includes(filter.toLowerCase()),
    )
    .sort((a, b) => {
      if (sort === "price")
        return (
          a.currency.localeCompare(b.currency) ||
          a.unit.localeCompare(b.unit) ||
          a.terms.unit_price_minor - b.terms.unit_price_minor ||
          a.id.localeCompare(b.id)
        );
      if (sort === "product")
        return (
          (product(a)?.title ?? a.terms.product_id).localeCompare(
            product(b)?.title ?? b.terms.product_id,
          ) || a.id.localeCompare(b.id)
        );
      return (
        a.expires_at.localeCompare(b.expires_at) || a.id.localeCompare(b.id)
      );
    });
  return (
    <section className="card">
      <h3 className="font-bold">Compare commercial offers</h3>
      <p className="mt-2 text-sm text-slate-500">
        Base prices exclude shared freight. Compare matching currencies, selling
        units and specifications; final delivered prices require clearing and
        your exact approval.
      </p>
      <div className="my-4 flex flex-wrap gap-3">
        <input
          className="field !mt-0 !w-auto"
          aria-label="Search commercial offers"
          placeholder="Product, request or note"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <select
          className="field !mt-0 !w-auto"
          aria-label="Filter commercial offer state"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All states</option>
          {Array.from(new Set(offers.map((o) => o.status)))
            .sort()
            .map((s) => (
              <option key={s} value={s}>
                State: {s}
              </option>
            ))}
        </select>
        <select
          className="field !mt-0 !w-auto"
          aria-label="Comparison request"
          value={buying}
          onChange={(e) => setBuying(e.target.value)}
        >
          <option value="">All requests</option>
          {Array.from(new Set(offers.map((o) => o.request_id))).map((id) => (
            <option key={id}>{id}</option>
          ))}
        </select>
        <select
          className="field !mt-0 !w-auto"
          aria-label="Sort commercial offers"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
        >
          <option value="expiry">Expiry, earliest first</option>
          <option value="price">Currency / unit, then lowest base price</option>
          <option value="product">Product name</option>
        </select>
      </div>
      <div className="overflow-x-auto">
        <table
          className="w-full text-left text-sm"
          aria-label="Commercial offer comparison"
        >
          <thead>
            <tr>
              {[
                "Product & specification",
                "Quantity",
                "Base price",
                "Buyer ceiling",
                "Expiry / state",
                "Review",
              ].map((h) => (
                <th className="border-b p-3" key={h}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => {
              const item = product(o);
              const need = data.requests.find((r) => r.id === o.request_id);
              return (
                <tr className="align-top" key={o.id}>
                  <td className="border-b p-3">
                    <b>{item?.title ?? o.terms.product_id}</b>
                    <p className="mt-1 text-xs text-slate-500">
                      {Object.entries(item?.attributes ?? {})
                        .map(([k, v]) => `${k}: ${v}`)
                        .join(" · ")}
                    </p>
                    {need && need.product_id !== o.terms.product_id && (
                      <p className="text-xs text-blue-800">
                        Buyer-permitted alternative
                      </p>
                    )}
                  </td>
                  <td className="border-b p-3">
                    {o.terms.quantity_min}–{o.terms.quantity_max} {o.unit}
                  </td>
                  <td className="border-b p-3">
                    {o.currency} {money(o.terms.unit_price_minor, o.currency)} /{" "}
                    {o.unit}
                    <p className="text-xs text-slate-500">Freight pending</p>
                  </td>
                  <td className="border-b p-3">
                    {need ? (
                      <>
                        {money(need.ceiling_minor, o.currency)} / {o.unit}
                        <p className="text-xs text-slate-500">
                          Delivered total limit
                        </p>
                      </>
                    ) : (
                      "See confirmed request"
                    )}
                  </td>
                  <td className="border-b p-3">
                    State: {o.status}
                    <p className="mt-1 text-xs">
                      {new Date(o.expires_at).toLocaleString()}
                    </p>
                    {new Date(o.expires_at).getTime() <= Date.now() && (
                      <p className="text-xs text-rose-800">
                        Expired · unavailable for acceptance
                      </p>
                    )}
                  </td>
                  <td className="border-b p-3">
                    <a
                      className="text-blue-700 underline"
                      href={`#offer-${o.id}`}
                    >
                      Review terms
                    </a>
                    <button
                      type="button"
                      className="mt-2 block text-blue-700 underline"
                      aria-label={`View revisions for ${o.id}`}
                      onClick={() => setHistory(o.id)}
                    >
                      View revisions
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!rows.length && (
        <p className="mt-4 text-sm text-slate-500">
          No commercial offers match these filters.
        </p>
      )}
      {history && (
        <div className="mt-4 rounded-xl border p-4">
          <div className="flex justify-between gap-3">
            <h4 className="font-bold">Offer revision history</h4>
            <button
              type="button"
              className="text-blue-700"
              onClick={() => setHistory("")}
            >
              Close revisions
            </button>
          </div>
          {revisions.isLoading && <p role="status">Loading revisions…</p>}
          {revisions.error && <p role="alert">{revisions.error.message}</p>}
          {revisions.data?.revisions
            .slice()
            .sort((a, b) => a.version - b.version)
            .map((r) => (
              <p className="mt-3 text-sm" key={r.version}>
                Version {r.version} · {r.status} when proposed · {r.currency}{" "}
                {money(r.terms.unit_price_minor, r.currency)} / {r.unit} ·{" "}
                {r.terms.quantity_min}–{r.terms.quantity_max} {r.unit} ·{" "}
                {r.terms.note}
              </p>
            ))}
          {revisions.data && (
            <p className="mt-3 text-xs text-slate-500">
              Current state: {revisions.data.status}. Historical proposals do
              not grant payment authority.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
