"use client";

import Link from "next/link";
import { Bell, ChevronDown, Menu, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { useSession } from "@/components/providers";
import { navByRole, roleLabel, roles, type Role } from "@/lib/roles";
import { OffersWorkbench } from "@/components/offers-workbench";
import { ProcurementCopilot } from "@/components/procurement-copilot";
import { MockModule } from "@/components/mock-module";
import { BuyerCatalog, NegotiationHub, ProductSheetUpload, RetailerHome, SellerCatalog, SellerHome } from "@/components/role-workflows";

function isRole(value: string): value is Role { return (roles as readonly string[]).includes(value); }

export function PortalShell({ routeRole, section }: { routeRole: string; section: string }) {
  const { roles: grantedRoles, activeRole, setActiveRole, isPreview, userName, signOut } = useSession();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [roleMenuOpen, setRoleMenuOpen] = useState(false);
  const roleCandidate = routeRole.toUpperCase();
  if (!isRole(roleCandidate) || !grantedRoles.includes(roleCandidate)) return <PermissionState isPreview={isPreview} />;
  const role = roleCandidate;
  const navigation = navByRole[role];
  const item = navigation.find((entry) => entry.segment === section) ?? navigation[0];
  const switchRole = (role: Role) => { if (grantedRoles.includes(role)) setActiveRole(role); };

  return <div className="min-h-screen bg-sand lg:flex">
    <aside className={`${sidebarOpen ? "block" : "hidden"} fixed inset-y-0 z-30 w-72 bg-ink p-5 text-white lg:static lg:block`}>
      <div className="flex items-center justify-between"><Link href={`/${routeRole}`} className="text-xl font-black">paypool</Link><button className="lg:hidden" onClick={() => setSidebarOpen(false)} aria-label="Close navigation">×</button></div>
      <p className="mt-2 text-xs text-blue-100">{isPreview ? `${userName ?? "Local user"} — local preview` : "Authenticated workspace"}</p>
      <nav className="mt-8 space-y-1">{navigation.map((entry) => <Link key={entry.segment} onClick={() => setSidebarOpen(false)} href={`/${routeRole}${entry.segment ? `/${entry.segment}` : ""}`} className={`block rounded-xl px-3 py-2.5 text-sm font-medium ${entry.segment === section ? "bg-blue-700 text-white" : "text-slate-300 hover:bg-white/10"}`}>{entry.label}</Link>)}</nav>
    </aside>
    <div className="min-w-0 flex-1"><header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-white/90 px-4 backdrop-blur lg:px-8"><button className="lg:hidden" onClick={() => setSidebarOpen(true)} aria-label="Open navigation"><Menu /></button><div className="hidden text-sm text-slate-500 lg:block">{roleLabel[role]} / <span className="font-semibold text-slate-800">{item.label}</span></div><div className="flex items-center gap-3"><button className="rounded-lg p-2 hover:bg-slate-100" aria-label="Notifications"><Bell size={18} /></button><div className="relative"><button className="btn-secondary !py-2 text-sm" onClick={() => setRoleMenuOpen((value) => !value)}>{activeRole ? roleLabel[activeRole] : "Account"} <ChevronDown size={15} /></button>{roleMenuOpen && <div className="absolute right-0 mt-2 w-52 rounded-xl border bg-white p-1 shadow-panel"><p className="px-3 py-2 text-xs text-slate-500">{userName ?? "Local user"}</p>{grantedRoles.map((role) => <Link key={role} href={`/${role.toLowerCase()}`} onClick={() => switchRole(role)} className="block rounded-lg px-3 py-2 text-sm hover:bg-slate-100">{roleLabel[role]}</Link>)}<button className="w-full rounded-lg px-3 py-2 text-left text-sm text-red-700 hover:bg-red-50" onClick={signOut}>Sign out</button></div>}</div></div></header>
      <main className="mx-auto max-w-7xl p-4 md:p-8"><PageHeader title={item.label} role={role} /><Module role={role} section={section} /></main>
    </div>
  </div>;
}

function PageHeader({ title, role }: { title: string; role: Role }) { return <div className="mb-7"><p className="text-sm font-semibold text-blue-700">{roleLabel[role]} workspace</p><h1 className="mt-1 text-3xl font-black tracking-tight text-ink">{title}</h1></div>; }

function Module({ role, section }: { role: Role; section: string }) {
  if (role === "RETAILER" && section === "procurement") return <ProcurementCopilot />;
  if (role === "RETAILER" && section === "catalog") return <BuyerCatalog />;
  if (role === "RETAILER" && section === "offers") return <><NegotiationHub /><details className="mt-6 rounded-xl border bg-white p-4 text-sm"><summary className="cursor-pointer font-semibold text-slate-700">Open live offer API test area</summary><div className="mt-4"><OffersWorkbench /></div></details></>;
  if (role === "SELLER" && section === "catalog") return <SellerCatalog />;
  if (role === "SELLER" && section === "upload-products") return <ProductSheetUpload />;
  if (role === "SELLER" && section === "offers") return <NegotiationHub seller />;
  if (!section && role === "RETAILER") return <RetailerHome />;
  if (!section && role === "SELLER") return <SellerHome />;
  if (!section) return <Overview role={role} />;
  return <MockModule role={role} section={section} label={navByRole[role].find((item) => item.segment === section)?.label ?? "Workspace"} />;
}

function Overview({ role }: { role: Role }) { return <MockModule role={role} section="overview" label="Operations overview" />; }

function PermissionState({ isPreview }: { isPreview: boolean }) { return <main className="grid min-h-screen place-items-center p-6"><section className="card max-w-lg text-center"><ShieldAlert className="mx-auto text-amber-600" size={36} /><h1 className="mt-4 text-2xl font-bold">This workspace is unavailable</h1><p className="mt-3 text-slate-600">{isPreview ? "This role is not granted in the local preview." : "Sign in to a backend-authorized PayPool role to access this workspace."}</p><Link href="/login" className="btn-primary mt-6">Return to sign in</Link></section></main>; }
