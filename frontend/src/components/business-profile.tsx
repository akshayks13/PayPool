"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession, type User } from "@/components/providers";
import { request, post } from "@/lib/http";

export type Application = {
  id?: string;
  version: number;
  status: string;
  business_name?: string;
  registration_number?: string;
  business_address?: string;
  contact_email?: string;
  contact_phone?: string;
  catalog_summary?: string;
  review_note?: string;
  submitted_at?: string;
};

export function BusinessProfile({ user }: { user: User }) {
  const client = useQueryClient();
  const { refreshSession } = useSession();
  const [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  useEffect(() => {
    if (!dirty) return;
    const unload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    const navigate = (e: MouseEvent) => {
      const a = (e.target as HTMLElement).closest?.("a");
      if (
        a?.href &&
        a.href !== window.location.href &&
        !window.confirm("Discard your unsaved profile changes?")
      ) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", unload);
    document.addEventListener("click", navigate, true);
    return () => {
      window.removeEventListener("beforeunload", unload);
      document.removeEventListener("click", navigate, true);
    };
  }, [dirty]);
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setMessage("");
    const f = new FormData(e.currentTarget);
    const payload: Record<string, unknown> = {
      name: f.get("name"),
      location: [Number(f.get("lon")), Number(f.get("lat"))],
      notifications_in_app: f.get("notifications_in_app") === "on",
    };
    for (const field of [
      "contact_email",
      "contact_phone",
      "business_address",
      "city",
      "postal_code",
      "country",
      "delivery_instructions",
      "preferred_delivery_window",
    ])
      payload[field] = String(f.get(field) ?? "");
    try {
      await request("/api/v1/me", {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setDirty(false);
      await refreshSession();
      await client.invalidateQueries({ queryKey: ["workspace"] });
      setMessage("Business profile saved.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not save profile");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="space-y-5">
      <section className="card max-w-3xl">
        <h2 className="text-xl font-bold">Business & delivery profile</h2>
        <p className="mt-2 text-sm text-slate-500">
          Account login: {user.email}. Contact and delivery details below apply
          to future agreements; approved orders retain their snapshots.
        </p>
        <form
          className="mt-5 grid gap-4 md:grid-cols-2"
          onChange={() => setDirty(true)}
          onSubmit={save}
        >
          {(
            [
              ["name", "Business name", user.name, "text"],
              [
                "contact_email",
                "Contact email",
                user.contact_email ?? "",
                "email",
              ],
              [
                "contact_phone",
                "Contact phone",
                user.contact_phone ?? "",
                "tel",
              ],
              [
                "business_address",
                "Delivery address",
                user.business_address ?? "",
                "text",
              ],
              ["city", "City", user.city ?? "", "text"],
              ["postal_code", "Postal code", user.postal_code ?? "", "text"],
              ["country", "Country", user.country ?? "", "text"],
              [
                "preferred_delivery_window",
                "Preferred delivery window",
                user.preferred_delivery_window ?? "",
                "text",
              ],
            ] as const
          ).map(([name, label, value, type]) => (
            <label className="label" key={name}>
              {label}
              <input
                className="field"
                name={name}
                type={type}
                defaultValue={value}
                maxLength={name === "business_address" ? 500 : 200}
                required={name === "name"}
              />
            </label>
          ))}
          <label className="label">
            Longitude
            <input
              className="field"
              name="lon"
              type="number"
              step="any"
              min="-180"
              max="180"
              required
              defaultValue={user.location[0]}
            />
          </label>
          <label className="label">
            Latitude
            <input
              className="field"
              name="lat"
              type="number"
              step="any"
              min="-90"
              max="90"
              required
              defaultValue={user.location[1]}
            />
          </label>
          <label className="label md:col-span-2">
            Delivery instructions
            <textarea
              className="field"
              name="delivery_instructions"
              defaultValue={user.delivery_instructions ?? ""}
              maxLength={500}
            />
          </label>
          <label className="flex gap-2 text-sm md:col-span-2">
            <input
              type="checkbox"
              name="notifications_in_app"
              defaultChecked={user.notifications_in_app !== false}
            />
            Receive routine in-app updates
          </label>
          <p className="text-xs text-slate-500 md:col-span-2">
            Payment, security and application-decision notifications remain
            enabled. Delivery address changes are locked while buying requests
            are active.
          </p>
          <button className="btn-primary" disabled={busy}>
            Save profile
          </button>
          {message && (
            <p role="status" className="text-sm md:col-span-2">
              {message}
            </p>
          )}
        </form>
      </section>
      <SellerApplicationPanel user={user} />
    </div>
  );
}

export function SellerApplicationPanel({ user }: { user: User }) {
  const client = useQueryClient();
  const { refreshSession } = useSession();
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const query = useQuery({
    queryKey: ["seller-application", user.id],
    queryFn: () => request<Application>("/api/v1/me/seller-application"),
    refetchInterval: 5000,
  });
  useEffect(() => {
    if (query.data?.status === "APPROVED" && !user.roles.includes("SELLER"))
      refreshSession();
  }, [query.data?.status, user.roles]);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const f = new FormData(e.currentTarget);
    try {
      await post("/api/v1/me/seller-application", Object.fromEntries(f));
      await client.invalidateQueries({ queryKey: ["seller-application"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit application");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card max-w-3xl">
      <h2 className="text-xl font-bold">Supplier application</h2>
      <p className="mt-2 text-sm text-slate-500">
        Apply to sell through PayPool. An administrator reviews your business
        details and grants supplier access; this does not onboard a PayPal
        merchant account.
      </p>
      {query.isLoading && (
        <p role="status" className="mt-3">
          Loading application…
        </p>
      )}
      {(query.error || error) && (
        <p role="alert" className="mt-3 text-red-800">
          {error || query.error?.message}
        </p>
      )}
      {query.data && (
        <p className="mt-3 text-sm font-bold">
          Application status:{" "}
          {user.roles.includes("SELLER") && user.verified
            ? "APPROVED"
            : query.data.status.replaceAll("_", " ")}
        </p>
      )}
      {query.data?.review_note && (
        <p className="mt-3 text-sm">Review note: {query.data.review_note}</p>
      )}
      {query.data &&
        !(user.roles.includes("SELLER") && user.verified) &&
        ["NOT_SUBMITTED", "REJECTED"].includes(query.data.status) && (
          <form className="mt-4 grid gap-4 md:grid-cols-2" onSubmit={submit}>
            {(
              [
                [
                  "business_name",
                  "Application business name",
                  query.data.business_name ?? user.name,
                  2,
                  200,
                ],
                [
                  "registration_number",
                  "Business registration / tax number",
                  query.data.registration_number ?? "",
                  3,
                  100,
                ],
                [
                  "business_address",
                  "Registered business address",
                  query.data.business_address ?? user.business_address ?? "",
                  5,
                  500,
                ],
                [
                  "contact_email",
                  "Application contact email",
                  query.data.contact_email ?? user.contact_email ?? user.email,
                  5,
                  200,
                ],
                [
                  "contact_phone",
                  "Application contact phone",
                  query.data.contact_phone ?? user.contact_phone ?? "",
                  3,
                  40,
                ],
              ] as const
            ).map(([name, label, value, min, max]) => (
              <label className="label" key={name}>
                {label}
                <input
                  className="field"
                  name={name}
                  defaultValue={value}
                  minLength={min}
                  maxLength={max}
                  required
                  type={name === "contact_email" ? "email" : "text"}
                />
              </label>
            ))}
            <label className="label md:col-span-2">
              Products and fulfillment capability
              <textarea
                className="field"
                name="catalog_summary"
                defaultValue={query.data.catalog_summary ?? ""}
                required
                minLength={10}
                maxLength={2000}
              />
            </label>
            <button className="btn-primary" disabled={busy}>
              Submit supplier application
            </button>
          </form>
        )}
    </section>
  );
}

export function SellerReviewQueue({
  act,
  busy,
}: {
  act: (path: string, data: unknown) => Promise<unknown>;
  busy: boolean;
}) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["seller-applications"],
    queryFn: () => request<Application[]>("/api/v1/admin/seller-applications"),
    refetchInterval: 5000,
  });
  const [error, setError] = useState("");
  async function review(e: FormEvent<HTMLFormElement>, a: Application) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const decision = String(f.get("decision"));
    if (
      !window.confirm(
        `${decision === "APPROVED" ? "Approve" : "Reject"} the application from ${a.business_name}?`,
      )
    )
      return;
    try {
      await act(`/api/v1/admin/seller-applications/${a.id}/review`, {
        version: a.version,
        decision,
        note: f.get("note"),
      });
      await client.invalidateQueries({ queryKey: ["seller-applications"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed");
    }
  }
  return (
    <section className="card">
      <h3 className="font-bold">Supplier application reviews</h3>
      {(query.error || error) && (
        <p role="alert">{error || query.error?.message}</p>
      )}
      {query.data?.length === 0 && (
        <p className="mt-3 text-sm text-slate-500">
          No supplier applications yet.
        </p>
      )}
      {query.data?.map((a) => (
        <article className="mt-4 rounded-xl border p-4" key={a.id}>
          <h4 className="font-bold">
            {a.business_name} · {a.status}
          </h4>
          <p className="mt-2 text-sm">Registration: {a.registration_number}</p>
          <p className="mt-1 text-sm">
            {a.business_address} · {a.contact_email} · {a.contact_phone}
          </p>
          <p className="mt-2 text-sm">{a.catalog_summary}</p>
          {a.review_note && (
            <p className="mt-2 text-sm">Review: {a.review_note}</p>
          )}
          {a.status === "PENDING" && (
            <form
              className="mt-4 flex flex-wrap gap-3"
              onSubmit={(e) => review(e, a)}
            >
              <select
                name="decision"
                aria-label={`Decision for ${a.business_name}`}
                className="field !w-auto"
              >
                <option value="APPROVED">Approve supplier access</option>
                <option value="REJECTED">Reject application</option>
              </select>
              <input
                className="field !w-auto"
                name="note"
                aria-label={`Review note for ${a.business_name}`}
                placeholder="Required review note"
                minLength={5}
                maxLength={1000}
                required
              />
              <button className="btn-primary" disabled={busy}>
                Save application decision
              </button>
            </form>
          )}
        </article>
      ))}
    </section>
  );
}
