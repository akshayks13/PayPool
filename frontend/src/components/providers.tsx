"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { post, request, setCsrf } from "@/lib/http";
import type { Role } from "@/lib/roles";
export type User = {
  id: string;
  name: string;
  email: string;
  roles: Role[];
  location: [number, number];
  verified: boolean;
};
type Session = {
  user: User;
  csrf: string;
  demo_mode: boolean;
  payment_provider: string;
};
type Context = {
  user: User | null;
  roles: Role[];
  activeRole: Role | null;
  setActiveRole: (role: Role) => void;
  isPreview: boolean;
  userName: string | null;
  loading: boolean;
  paymentProvider: string;
  signIn: (email: string, password: string) => Promise<User>;
  signOut: () => Promise<void>;
};
const SessionContext = createContext<Context | null>(null);
export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("Session provider missing");
  return value;
}
export function AppProviders({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient());
  const [session, setSession] = useState<Session | null>(null);
  const [activeRole, setActiveRole] = useState<Role | null>(null);
  const [loading, setLoading] = useState(true);
  const accept = (value: Session) => {
    setCsrf(value.csrf);
    setSession(value);
    setActiveRole(value.user.roles[0]);
  };
  useEffect(() => {
    request<Session>("/api/v1/me")
      .then(accept)
      .catch(() => setSession(null))
      .finally(() => setLoading(false));
  }, []);
  const signIn = async (email: string, password: string) => {
    const value = await post<Session>("/api/v1/auth/login", {
      email,
      password,
    });
    client.clear();
    accept(value);
    return value.user;
  };
  const signOut = async () => {
    try {
      await post("/api/v1/auth/logout");
    } finally {
      setCsrf("");
      setSession(null);
      setActiveRole(null);
      client.clear();
      window.location.assign("/login");
    }
  };
  return (
    <QueryClientProvider client={client}>
      <SessionContext.Provider
        value={{
          user: session?.user ?? null,
          roles: session?.user.roles ?? [],
          activeRole,
          setActiveRole,
          isPreview: session?.demo_mode ?? false,
          userName: session?.user.name ?? null,
          loading,
          paymentProvider: session?.payment_provider ?? "unavailable",
          signIn,
          signOut,
        }}
      >
        {children}
      </SessionContext.Provider>
    </QueryClientProvider>
  );
}
