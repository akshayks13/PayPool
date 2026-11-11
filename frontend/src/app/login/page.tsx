"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { useSession } from "@/components/providers";
import { request } from "@/lib/http";
type Config = {
  demo_mode: boolean;
  paypal_login_enabled: boolean;
  demo_password: string | null;
  payment_provider: string;
  accounts: { id: string; email: string; name: string; roles: string[] }[];
};
export default function LoginPage() {
  const { signIn } = useSession();
  const router = useRouter();
  const [config, setConfig] = useState<Config | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    request<Config>("/api/v1/config")
      .then(setConfig)
      .catch(() =>
        setError(
          "Cannot reach the backend. Start FastAPI on port 8000 and retry.",
        ),
      );
  }, []);
  async function login(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const user = await signIn(email, password);
      router.push(`/${user.roles[0].toLowerCase()}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="min-h-screen bg-[radial-gradient(ellipse_at_top_left,_#dbeafe,_#f8fbff_60%)] px-5 py-12">
      <div className="mx-auto grid max-w-5xl gap-12 lg:grid-cols-2 lg:items-center">
        <section>
          <Link href="/" className="text-2xl font-black text-blue-800">
            paypool<span className="text-blue-400">.</span>
          </Link>
          <p className="mt-12 text-sm font-bold uppercase tracking-widest text-blue-600">
            Independent shops. Shared buying power.
          </p>
          <h1 className="mt-4 text-4xl font-black leading-tight text-ink">
            A better delivery run starts with a better agreement.
          </h1>
          <p className="mt-5 leading-8 text-slate-600">
            Bring your demand together, see every delivery charge, and approve
            only an order that fits your limit.
          </p>
          <div className="mt-8 grid grid-cols-3 gap-3">
            {["Buyer control", "Shared freight", "Verified receipts"].map(
              (t) => (
                <div
                  className="rounded-xl border bg-white/70 p-3 text-sm font-semibold"
                  key={t}
                >
                  {t}
                </div>
              ),
            )}
          </div>
        </section>
        <section className="card">
          <h2 className="text-2xl font-black">Welcome to PayPool</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            Your workspace permissions come from your account.
          </p>
          {config?.demo_mode && (
            <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <b>Hackathon demo environment</b>
              <p className="mt-1">
                Fictional businesses and supplier prices.{" "}
                {config.payment_provider === "demo"
                  ? "Payments are simulated and clearly labelled."
                  : "Checkout uses PayPal sandbox test accounts."}
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {config.accounts.map((a) => (
                  <button
                    key={a.id}
                    className="rounded-lg border border-amber-200 bg-white p-2 text-left text-xs hover:border-blue-500"
                    onClick={() => {
                      setEmail(a.email);
                      setPassword(config.demo_password ?? "");
                    }}
                  >
                    <b>{a.name}</b>
                    <span className="mt-1 block text-slate-500">
                      {a.roles.join(", ")}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
          <form onSubmit={login} className="mt-6 space-y-4">
            <label className="label block">
              Email
              <input
                type="email"
                required
                className="field"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
              />
            </label>
            <label className="label block">
              Password
              <input
                type="password"
                required
                className="field"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </label>
            {error && (
              <p
                role="alert"
                className="rounded-lg bg-red-50 p-3 text-sm text-red-800"
              >
                {error}
              </p>
            )}
            <button className="btn-primary w-full" disabled={busy || !config}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>
          {config?.paypal_login_enabled && (
            <a
              href="/api/v1/auth/paypal/start"
              className="btn-secondary mt-3 w-full"
            >
              Log in with PayPal sandbox
            </a>
          )}
        </section>
      </div>
    </main>
  );
}
