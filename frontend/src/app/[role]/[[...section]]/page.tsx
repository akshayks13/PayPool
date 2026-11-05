"use client";

import { useParams } from "next/navigation";
import { PortalShell } from "@/components/portal-shell";

export default function RolePortalPage() {
  const params = useParams<{ role: string; section?: string[] }>();
  return <PortalShell routeRole={params.role} section={params.section?.[0] ?? ""} />;
}
