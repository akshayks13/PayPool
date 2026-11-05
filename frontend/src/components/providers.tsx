"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useState, type ReactNode } from "react";
import type { Role } from "@/lib/roles";

type SessionContextValue = {
  roles: Role[];
  activeRole: Role | null;
  setActiveRole: (role: Role) => void;
  isPreview: boolean;
  userName: string | null;
  signInPreview: (userName: string, role: Role) => void;
  signOut: () => void;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used within AppProviders");
  return context;
}

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  const [activeRole, setActiveRole] = useState<Role | null>(null);
  const [userName, setUserName] = useState<string | null>(null);
  // Temporary until the backend session/bootstrap routes are available.
  // The form itself is intentionally local-only and never stores credentials.
  const isPreview = true;
  const roles = isPreview && activeRole ? [activeRole] : [];
  const signInPreview = (name: string, role: Role) => { setUserName(name); setActiveRole(role); };
  const signOut = () => { setUserName(null); setActiveRole(null); };

  return (
    <QueryClientProvider client={queryClient}>
      <SessionContext.Provider value={{ roles, activeRole, setActiveRole, isPreview, userName, signInPreview, signOut }}>
        {children}
      </SessionContext.Provider>
    </QueryClientProvider>
  );
}
