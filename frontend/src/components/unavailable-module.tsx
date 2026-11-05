import { CircleDashed, LockKeyhole } from "lucide-react";
import type { Role } from "@/lib/roles";

export function UnavailableModule({ role, module }: { role: Role; module: string }) {
  return <section className="card max-w-3xl"><div className="flex items-start gap-4"><div className="rounded-xl bg-slate-100 p-3 text-slate-600"><CircleDashed /></div><div><h2 className="font-bold">{module} is ready for its backend contract</h2><p className="mt-2 leading-6 text-slate-600">The {role.toLowerCase()} UI shell, responsive navigation, loading/empty/error conventions, and permission boundary are in place. This page intentionally does not fabricate catalog, order, pool, dispatch, POD, payment, or audit data.</p></div></div><div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"><LockKeyhole className="mr-2 inline" size={16} /><b>Integration blocked:</b> this backend endpoint has not been implemented or finalized in the shared contract.</div></section>;
}
