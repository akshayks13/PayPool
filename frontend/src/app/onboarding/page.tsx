"use client";
import Link from "next/link";
import { useSession } from "@/components/providers";
import { SellerApplicationPanel } from "@/components/business-profile";

export default function Onboarding() {
  const { user, loading, signOut } = useSession();
  if (loading)
    return (
      <main className="grid min-h-screen place-items-center">
        Loading your account…
      </main>
    );
  return (
    <main className="grid min-h-screen place-items-center bg-sand p-6">
      <section className="card max-w-lg">
        <h1 className="text-2xl font-bold">Your PayPool account</h1>
        <p className="mt-4 text-sm leading-7 text-slate-600">
          {!user
            ? "Sign in to set up your buying workspace."
            : user.roles.length
              ? "Complete your business name and delivery location before requesting a supplier offer."
              : "Your identity is confirmed. An administrator must grant your business a role before this workspace can open."}
        </p>
        <div className="mt-5 flex gap-3">
          {user?.roles.length ? (
            <Link
              className="btn-primary"
              href={`/${user.roles[0].toLowerCase()}/settings`}
            >
              Complete business profile
            </Link>
          ) : !user ? (
            <Link href="/login" className="btn-primary">
              Sign in
            </Link>
          ) : null}
          {user && (
            <button className="btn-secondary" onClick={() => signOut()}>
              Sign out
            </button>
          )}
        </div>
        {user && (
          <div className="mt-6">
            <SellerApplicationPanel user={user} />
          </div>
        )}
      </section>
    </main>
  );
}
