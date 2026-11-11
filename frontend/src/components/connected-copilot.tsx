"use client";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Bot, Send, ShieldCheck } from "lucide-react";
import { post, request as read } from "@/lib/http";
import { money, type Product, type Workspace } from "@/lib/commerce";
import type { ProcurementIntent } from "@/lib/api";
import { BuyingForm } from "@/components/commerce-workspace";

type Discovery = {
  conversation?: Conversation | null;
  intent: ProcurementIntent;
  engine: string;
  agent_trace?: {
    buyer: { status: string; recommended_product_id: string | null };
    distributor: { product_id: string; status: string }[];
    execution: string;
  };
  narration_error?: string;
  messages: { speaker: string; message: string }[];
  candidates: {
    product_id: string;
    zone_id: string;
    title: string;
    quantity: number;
    unit: string;
    currency: string;
    estimated_total_minor: number;
    standalone_total_minor: number;
    within_ceiling: boolean;
    pool_quantity: number;
    other_requests: number;
    next_tier: { minimum_quantity: number; unit_price_minor: number } | null;
  }[];
};
type Conversation = {
  version: number;
  message: string;
  intent: ProcurementIntent | null;
  engine: string | null;
  updated_at: string | null;
  history: { message: string; questions: string[]; at: string }[];
};
type Props = {
  data: Workspace;
  act: (path: string, data?: unknown) => Promise<unknown>;
  busy: boolean;
};
export function ConnectedCopilot({ data, act, busy }: Props) {
  const [draft, setDraft] = useState("");
  const [result, setResult] = useState<Discovery | null>(null);
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Product | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [message, setMessage] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(true);
  const [restored, setRestored] = useState(false);
  useEffect(() => {
    let active = true;
    read<Conversation>("/api/v1/procurement/conversation")
      .then((saved) => {
        if (!active) return;
        setConversation(saved);
        setMessage(saved.message);
        if (saved.intent) {
          setCurrency(saved.intent.currency);
          setResult({
            intent: saved.intent,
            engine: saved.engine ?? "deterministic",
            candidates: [],
            messages: [],
          });
          setRestored(true);
        }
      })
      .catch((e) => {
        if (active)
          setError(
            e instanceof Error
              ? e.message
              : "Could not restore the buying task",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [data.user.id]);
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!draft.trim()) return;
    // A clarification answers the current request; a completed comparison starts
    // a new one. Keep the original requirements when the buyer supplies omissions.
    const request = result?.intent.clarification_questions.length
      ? `${message}\n${draft.trim()}`
      : draft.trim();
    if (request.length > 1000) {
      setError(
        "This request is too long. Start a new request with your combined requirements (up to 1,000 characters).",
      );
      return;
    }
    await compare(request);
  }
  async function compare(request: string) {
    if (!conversation) return;
    setThinking(true);
    setError("");
    setSubmitted(false);
    setSelected(null);
    try {
      const discovery = await post<Discovery>("/api/v1/procurement/discover", {
        message: request,
        currency,
        conversation_version: conversation.version,
      });
      setResult(discovery);
      setMessage(request);
      setDraft("");
      setConversation(discovery.conversation ?? null);
      setRestored(false);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not interpret the request",
      );
    } finally {
      setThinking(false);
    }
  }
  async function reset(example = "") {
    if (!conversation) return;
    setThinking(true);
    try {
      const saved = await post<Conversation>(
        "/api/v1/procurement/conversation/reset",
        { version: conversation.version },
      );
      setConversation(saved);
      setDraft(example);
      if (example) setCurrency("USD");
      setResult(null);
      setMessage("");
      setSelected(null);
      setSubmitted(false);
      setRestored(false);
      setError("");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not reset the saved task",
      );
    } finally {
      setThinking(false);
    }
  }
  return (
    <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
      <section className="overflow-hidden rounded-2xl border bg-white shadow-panel">
        <header className="flex items-center gap-3 bg-ink p-5 text-white">
          <Bot size={24} />
          <div>
            <h2 className="font-bold">Buy with PayPool</h2>
            <p className="text-xs text-blue-200">
              Your requirements. Your delivered-price limit.
            </p>
          </div>
        </header>
        <div className="min-h-60 space-y-4 bg-slate-50 p-5">
          {loading && <p role="status">Restoring your saved buying task…</p>}
          {restored && (
            <div className="rounded-xl border bg-blue-50 p-4 text-sm text-blue-900">
              <p>
                Saved requirements restored. Prices and availability must be
                checked again before creating a request.
              </p>
              <button
                type="button"
                className="btn-secondary mt-3"
                disabled={thinking}
                onClick={() => compare(message)}
              >
                Refresh saved comparison
              </button>
            </div>
          )}
          {!!conversation?.history.length && (
            <details className="rounded-xl border bg-white p-4 text-sm">
              <summary>Saved conversation history</summary>
              {conversation.history.map((turn, i) => (
                <div className="mt-3 border-t pt-3" key={`${turn.at}-${i}`}>
                  <p className="whitespace-pre-wrap">{turn.message}</p>
                  {turn.questions.map((q) => (
                    <p className="mt-1 text-amber-900" key={q}>
                      PayPool asked: {q}
                    </p>
                  ))}
                </div>
              ))}
            </details>
          )}
          <p className="max-w-xl rounded-xl border bg-white p-4 text-sm leading-7">
            Tell me the product, quantity, delivery date and the most you can
            pay including delivery. I’ll compare the supplier catalog and shared
            demand. You confirm the request before it joins a pool.
          </p>
          {message && (
            <p className="ml-auto max-w-xl whitespace-pre-wrap rounded-xl bg-blue-700 p-4 text-sm text-white">
              {message}
            </p>
          )}
          {thinking && (
            <p role="status" className="animate-pulse text-sm text-blue-700">
              Checking requirements, supplier tiers, available stock and
              delivery area…
            </p>
          )}
          {error && (
            <div
              role="alert"
              className="rounded-xl bg-rose-50 p-4 text-sm text-rose-900"
            >
              {error}
              <p className="mt-2">
                You can also{" "}
                <Link className="underline" href="/retailer/catalog">
                  create a request directly from the catalog
                </Link>
                .
              </p>
            </div>
          )}
          {result && (
            <>
              {result.agent_trace && (
                <details className="rounded-xl border bg-white p-4 text-sm">
                  <summary className="cursor-pointer font-bold">
                    Buyer & supplier checks
                  </summary>
                  <p className="mt-3">
                    Buyer recommendation:{" "}
                    {result.agent_trace.buyer.status.replaceAll("_", " ")}
                  </p>
                  <p className="mt-2 text-xs text-slate-500">
                    Supplier policies checked for{" "}
                    {result.agent_trace.distributor.length} eligible catalog
                    offers. Exact pool approval is still required.
                  </p>
                </details>
              )}
              <p className="text-xs font-bold uppercase tracking-widest text-slate-400">
                {result.engine === "gemini"
                  ? "Gemini-assisted interpretation · server-validated estimates"
                  : "Offline rules-based interpretation · no model call"}
              </p>
              {result.narration_error && (
                <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
                  AI narration unavailable: {result.narration_error}. The
                  supplier calculations below remain rules-based estimates.
                </p>
              )}
              {result.intent.clarification_questions.map((q) => (
                <p
                  key={q}
                  className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900"
                >
                  {q}
                </p>
              ))}
              {result.messages.map((m, i) => (
                <div
                  key={i}
                  className={`max-w-xl rounded-xl border p-4 text-sm leading-6 ${m.speaker.includes("Distributor") ? "ml-auto bg-blue-50" : "bg-white"}`}
                >
                  <b className="mb-1 block text-xs text-blue-700">
                    {m.speaker}
                  </b>
                  {m.message}
                </div>
              ))}
              {!result.candidates.length &&
                !restored &&
                !result.intent.clarification_questions.length && (
                  <p className="rounded-xl bg-white p-4 text-sm">
                    No eligible catalog match in your service area. Check the
                    product, selling unit, currency and delivery location.
                  </p>
                )}
            </>
          )}
        </div>
        <form onSubmit={submit} className="border-t p-4">
          <label className="mb-3 flex items-center gap-3 text-sm font-semibold">
            Buying currency
            <select
              className="field !mt-0 !w-auto"
              aria-label="Buying currency"
              value={currency}
              disabled={thinking || loading}
              onChange={(e) => setCurrency(e.target.value)}
            >
              {["USD", "EUR", "GBP", "INR"].map((code) => (
                <option key={code}>{code}</option>
              ))}
            </select>
          </label>
          {(message || result) && (
            <button
              type="button"
              className="mb-3 mr-3 text-sm font-semibold text-blue-700"
              disabled={thinking || loading || !conversation}
              onClick={() => reset()}
            >
              Start a new request
            </button>
          )}
          <button
            type="button"
            className="mb-3 rounded-full bg-blue-50 px-3 py-2 text-left text-xs text-blue-800"
            disabled={thinking || loading || !conversation}
            onClick={() =>
              reset(
                `I need 30 kg Sona Masoori rice by ${tomorrow}, landed price below USD 1.70/kg.`,
              )
            }
          >
            Try a shared rice order within $1.70/kg
          </button>
          <div className="flex gap-2">
            <textarea
              aria-label="Buying request"
              value={draft}
              disabled={thinking || loading || !conversation}
              onChange={(e) => setDraft(e.target.value)}
              className="field min-h-20"
              placeholder="I need 30 kg rice by YYYY-MM-DD, landed price below USD 1.70/kg…"
              maxLength={1000}
            />
            <button
              className="btn-primary mt-1"
              disabled={thinking || loading || !conversation || !draft.trim()}
              aria-label="Compare supplier offers"
            >
              <Send size={18} />
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {result?.intent.clarification_questions.length
              ? "Your reply will be added to the request above. Start a new request to replace it. "
              : ""}
            Demo products use USD. Your selected currency must match the
            supplier's catalog. INR payments are simulation only.
          </p>
        </form>
      </section>
      <aside className="space-y-4">
        {result?.candidates.map((c) => (
          <article className="card" key={`${c.product_id}-${c.zone_id}`}>
            <div className="flex items-center gap-2 text-blue-700">
              <ShieldCheck size={18} />
              <b className="text-sm">Supplier-backed estimate</b>
            </div>
            <h3 className="mt-4 font-bold">{c.title}</h3>
            <p className="mt-3 text-2xl font-black">
              {money(c.estimated_total_minor, c.currency)}
              <span className="ml-2 text-xs font-normal text-slate-500">
                for {c.quantity} {c.unit}, including estimated freight
              </span>
            </p>
            <p className="mt-2 text-sm text-slate-500">
              Standalone estimate {money(c.standalone_total_minor, c.currency)}{" "}
              · {c.other_requests} existing matching requests
            </p>
            <p
              className={`mt-3 rounded-lg p-3 text-sm ${c.within_ceiling ? "bg-emerald-50 text-emerald-900" : "bg-amber-50 text-amber-900"}`}
            >
              {c.within_ceiling
                ? "Estimate fits your ceiling; final pool clearing is still required."
                : "Not affordable yet. More compatible demand or a seller-approved change is needed."}
            </p>
            {c.next_tier && (
              <p className="mt-3 text-xs text-slate-500">
                Next configured tier: {c.next_tier.minimum_quantity} {c.unit} at{" "}
                {money(c.next_tier.unit_price_minor, c.currency)} / {c.unit}.
                Not earned yet.
              </p>
            )}
            <button
              className="btn-primary mt-4 w-full"
              onClick={() =>
                setSelected(
                  data.products.find((p) => p.id === c.product_id) ?? null,
                )
              }
            >
              Review product & create request
            </button>
          </article>
        ))}
        {selected && result && (
          <article className="card">
            <h3 className="font-bold">Confirm your buying request</h3>
            <p className="mt-2 text-xs text-slate-500">
              Actual catalog attributes: {JSON.stringify(selected.attributes)}
            </p>
            <BuyingForm
              data={data}
              act={act}
              busy={busy}
              product={selected}
              initialQuantity={Number(result.intent.quantity ?? 30)}
              initialCeiling={
                (result.intent.price_ceiling_per_unit_minor ?? 170) / 100
              }
              initialTarget={
                result?.intent.target_price_per_unit_minor != null
                  ? result.intent.target_price_per_unit_minor / 100
                  : undefined
              }
              initialDate={result.intent.delivery_date ?? undefined}
              onDone={() => {
                setSelected(null);
                setSubmitted(true);
              }}
            />
          </article>
        )}
        {submitted && (
          <article className="card bg-emerald-50 text-emerald-900">
            <b>Your request has joined a delivery pool.</b>
            <p className="mt-2 text-sm">
              The distributor can now calculate the final shared allocation.
            </p>
            <Link className="btn-primary mt-4" href="/retailer/pools">
              View shared delivery
            </Link>
          </article>
        )}
        {!result && (
          <article className="card">
            <h3 className="font-bold">The price limit includes delivery</h3>
            <p className="mt-3 text-sm leading-7 text-slate-500">
              An attractive product price can become expensive after freight.
              PayPool checks the combined cost and asks for your approval on the
              final allocation.
            </p>
          </article>
        )}
      </aside>
    </div>
  );
}
