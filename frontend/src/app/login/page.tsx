"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { LockKeyhole } from "lucide-react";
import { useSession } from "@/components/providers";
import { roleLabel, roles, type Role } from "@/lib/roles";

export default function LoginPage() {
  const router = useRouter();
  const { signInPreview, isPreview } = useSession();
  const [error, setError] = useState("");
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const userName = String(form.get("userName") ?? "").trim();
    const password = String(form.get("password") ?? "");
    const role = String(form.get("role") ?? "") as Role;
    if (!userName || !password || !roles.includes(role)) { setError("Enter a username, password, and the workspace role you need."); return; }
    signInPreview(userName, role);
    router.push(`/${role.toLowerCase()}`);
  };
  return (
    <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_top_right,_#dbeafe,_#f8fbff_55%)] p-6"><section className="card w-full max-w-md"><Link href="/" className="text-xl font-black text-moss">paypool</Link><div className="mt-8"><span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-800">LOCAL DEMO SIGN-IN</span><h1 className="mt-4 text-3xl font-black text-ink">Enter your workspace</h1><p className="mt-3 text-sm leading-6 text-slate-600">Choose the role you are working as today. This is a temporary local form; PayPal Login and backend role validation will replace it.</p></div>{isPreview ? <form className="mt-7 space-y-5" onSubmit={submit}><div><label className="label" htmlFor="user-name">Username</label><input id="user-name" name="userName" className="field" placeholder="e.g. anika@greenmart" autoComplete="username" /></div><div><label className="label" htmlFor="password">Password</label><input id="password" name="password" type="password" className="field" placeholder="Enter any password for local preview" autoComplete="current-password" /></div><div><label className="label" htmlFor="role">I am signing in as</label><select id="role" name="role" className="field" defaultValue=""><option value="" disabled>Select your workspace role</option>{roles.map((role) => <option key={role} value={role}>{roleLabel[role]}{role === "SELLER" ? " / Wholesaler" : ""}</option>)}</select></div>{error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{error}</p>}<button className="btn-primary w-full"><LockKeyhole size={17} /> Sign in to workspace</button></form> : <div className="mt-7 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">Local preview is disabled. PayPal Login will appear here when backend authentication is connected.</div>}<p className="mt-6 text-xs leading-5 text-slate-500">This demo does not store passwords or grant real permissions. In production, roles come only from PayPool&apos;s backend membership checks.</p></section></main>
  );
}
