"use client";

import Link from "next/link";
import { Brand } from "@/components/brand";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useSession } from "@/components/providers";
import { post } from "@/lib/http";

export default function SignUp() {
  const router = useRouter();
  const { refreshSession } = useSession();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await post("/api/v1/auth/register", {
        name: fields.get("name"),
        email: fields.get("email"),
        password: fields.get("password"),
      });
      await refreshSession();
      router.push("/retailer/settings");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not create your account",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="min-h-screen bg-sand px-5 py-12">
      <section className="card mx-auto max-w-lg">
        <Link href="/" aria-label="PayPool home">
          <Brand />
        </Link>
        <h1 className="mt-8 text-3xl font-black">
          Create your buying workspace
        </h1>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          Try PayPool with your own retailer account. This is a sandbox
          demonstration with test payments and fictional supplier prices.
        </p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="label block">
            Business name
            <input
              name="name"
              className="field"
              required
              minLength={2}
              maxLength={200}
              autoComplete="organization"
            />
          </label>
          <label className="label block">
            Business email
            <input
              name="email"
              type="email"
              className="field"
              required
              maxLength={200}
              autoComplete="email"
            />
          </label>
          <label className="label block">
            Password
            <input
              name="password"
              type="password"
              className="field"
              required
              minLength={12}
              maxLength={128}
              autoComplete="new-password"
            />
            <span className="mt-1 block text-xs text-slate-500">
              At least 12 characters.
            </span>
          </label>
          <p className="rounded-xl bg-blue-50 p-3 text-sm leading-6 text-blue-900">
            Your demo shop starts in the South Bengaluru delivery area. You can
            edit its business and delivery profile after signing up. Supplier
            access requires an application and administrator approval.
          </p>
          {error && (
            <p
              role="alert"
              className="rounded-xl bg-red-50 p-3 text-sm text-red-800"
            >
              {error}
            </p>
          )}
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>
        <p className="mt-6 text-sm text-slate-600">
          Already registered?{" "}
          <Link href="/login" className="font-semibold text-blue-700 underline">
            Sign in
          </Link>
        </p>
      </section>
    </main>
  );
}
