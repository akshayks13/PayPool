"use client";

import { loadScript, type PayPalNamespace } from "@paypal/paypal-js";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { request } from "@/lib/http";
import type { Order } from "@/lib/commerce";

const scripts = new Map<string, Promise<PayPalNamespace | null>>();
function sdk(clientId: string, currency: string) {
  const key = `${clientId}:${currency}`;
  if (!scripts.has(key)) {
    scripts.set(
      key,
      loadScript({
        clientId,
        environment: "sandbox",
        currency,
        intent: "authorize",
        commit: false,
        components: ["buttons"],
        disableFunding: ["card", "credit", "paylater", "venmo"],
        dataNamespace: `paypoolPayPal${currency}`,
      }).catch((error) => {
        scripts.delete(key);
        throw error;
      }),
    );
  }
  return scripts.get(key)!;
}

type Props = {
  order: Order;
  busy: boolean;
  act: (path: string) => Promise<unknown>;
};

export function PayPalCheckout({ order, busy, act }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const latest = useRef({ order, busy, act });
  latest.current = { order, busy, act };
  const [message, setMessage] = useState("");
  const [ready, setReady] = useState(false);
  const [retry, setRetry] = useState(0);
  const config = useQuery({
    queryKey: ["paypal-checkout-config"],
    queryFn: () =>
      request<{ paypal_client_id: string | null }>("/api/v1/config"),
    staleTime: 60_000,
  });
  const clientId = config.data?.paypal_client_id;

  useEffect(() => {
    if (!clientId || !container.current) return;
    let disposed = false;
    let close: (() => Promise<void>) | undefined;
    setReady(false);
    setMessage("");
    const slowLoad = window.setTimeout(() => {
      if (!disposed)
        setMessage(
          "PayPal is taking longer to load. You can wait, reload PayPal, or use full-page checkout below.",
        );
    }, 25_000);
    sdk(clientId, order.currency)
      .then(async (paypal) => {
        if (disposed || !container.current) return;
        if (!paypal?.Buttons) throw new Error("PayPal buttons are unavailable");
        const buttons = paypal.Buttons({
          fundingSource: "paypal",
          style: {
            layout: "vertical",
            color: "gold",
            shape: "rect",
            label: "paypal",
            height: 45,
          },
          onClick: (_data, actions) => {
            if (latest.current.busy) return actions.reject();
            setMessage("Opening PayPal checkout…");
            return actions.resolve();
          },
          createOrder: async () => {
            const result = (await latest.current.act(
              `/api/v1/orders/${order.id}/checkout`,
            )) as Order;
            if (
              result.payment_error ||
              !result.provider_order_id ||
              result.provider_order_id.startsWith("DEMO-")
            ) {
              throw new Error(
                result.payment_error || "PayPal checkout could not be created",
              );
            }
            return result.provider_order_id;
          },
          onApprove: async (data) => {
            const result = (await latest.current.act(
              `/api/v1/orders/${order.id}/authorize`,
            )) as Order;
            if (
              result.provider_order_id !== data.orderID ||
              result.payment_status !== "AUTHORIZED"
            ) {
              throw new Error(
                result.payment_error ||
                  "PayPal approval needs reconciliation. Check the order status before retrying.",
              );
            }
          },
          onCancel: () => {
            if (!disposed)
              setMessage("Checkout closed. You can try again when ready.");
          },
          onError: () => {
            if (!disposed)
              setMessage(
                "PayPal checkout could not finish. Check the order status before retrying, or use full-page checkout below.",
              );
          },
        });
        close = () => buttons.close();
        if (!buttons.isEligible())
          throw new Error("PayPal checkout is unavailable in this browser");
        await buttons.render(container.current);
        if (!disposed) {
          window.clearTimeout(slowLoad);
          setMessage("");
          setReady(true);
        }
      })
      .catch(() => {
        window.clearTimeout(slowLoad);
        if (!disposed)
          setMessage(
            "Could not load PayPal. Check your connection or use full-page checkout below.",
          );
      });
    return () => {
      disposed = true;
      window.clearTimeout(slowLoad);
      void close?.().catch(() => {});
    };
  }, [clientId, order.id, order.currency, retry]);

  async function fullPageCheckout() {
    try {
      const result = (await latest.current.act(
        `/api/v1/orders/${order.id}/checkout`,
      )) as Order;
      if (result.payment_error || !result.approval_url)
        throw new Error("Checkout is unavailable");
      window.location.assign(result.approval_url);
    } catch {
      setMessage(
        "Could not open checkout. Check the order status and try again.",
      );
    }
  }

  return (
    <div className="w-full max-w-sm space-y-3">
      <div
        className="relative z-0 min-h-[45px]"
        ref={container}
        style={{
          opacity: ready ? 1 : 0,
          pointerEvents: ready ? "auto" : "none",
        }}
        aria-busy={!ready}
      />
      {!ready && !message && (
        <p className="text-sm text-slate-500">
          {config.isError || (config.isSuccess && !clientId)
            ? "PayPal checkout is not configured."
            : "Loading secure PayPal checkout…"}
        </p>
      )}
      <p className="text-xs leading-5 text-slate-500">
        Sandbox test payment. Approve in the PayPal window, then continue here.
        Your payment is authorized first; capture follows confirmed delivery.
      </p>
      {message && (
        <p
          role="status"
          className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900"
        >
          {message}
        </p>
      )}
      {message && !ready && (
        <button
          className="btn-secondary text-sm"
          disabled={busy}
          onClick={() => {
            void config.refetch();
            setRetry((value) => value + 1);
          }}
        >
          Reload PayPal
        </button>
      )}
      <details className="text-xs text-slate-500">
        <summary className="cursor-pointer">
          Having trouble opening PayPal?
        </summary>
        <button
          className="mt-2 font-semibold text-blue-700 underline"
          disabled={busy}
          onClick={fullPageCheckout}
        >
          Use full-page checkout
        </button>
      </details>
    </div>
  );
}
