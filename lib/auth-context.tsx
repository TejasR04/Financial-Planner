"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, setAuthToken, setUnauthorizedHandler, setDemoMode } from "@/lib/api-client";

type AuthState = {
  status: "loading" | "authenticated" | "unauthenticated";
  error: string | null;
  isDemo: boolean;
  toggleDemo: () => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [status, setStatus] = useState<AuthState["status"]>("loading");
  const [error, setError] = useState<string | null>(null);
  const [isDemo, setIsDemo] = useState(false);
  const toggleDemo = useCallback(() => {
    const next = !isDemo;
    setDemoMode(next);
    setIsDemo(next);
    try { sessionStorage.setItem("meridian-demo", String(next)); } catch {}
    router.push(next || status === "authenticated" ? "/" : "/login");
  }, [isDemo, router, status]);
  const authGeneration = useRef(0);

  const clearSession = useCallback(() => {
    authGeneration.current += 1;
    setDemoMode(false);
    setIsDemo(false);
    try { sessionStorage.removeItem("meridian-demo"); } catch {}
    setAuthToken(null);
    setStatus("unauthenticated");
    router.push("/login");
  }, [router]);

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } finally {
      clearSession();
    }
  }, [clearSession]);

  useEffect(() => {
    setUnauthorizedHandler(clearSession);
    return () => setUnauthorizedHandler(null);
  }, [clearSession]);

  // Restore the session from the HttpOnly refresh cookie. Access tokens only
  // live in memory, which prevents browser scripts from reading long-lived credentials.
  useEffect(() => {
    try {
      if (sessionStorage.getItem("meridian-demo") === "true") {
        setDemoMode(true);
        setIsDemo(true);
      }
    } catch {}
    const generation = ++authGeneration.current;
    api.auth.refresh()
      .then((tokens) => {
        if (authGeneration.current !== generation) return;
        setAuthToken(tokens.access_token);
        setStatus("authenticated");
      })
      .catch(() => {
        if (authGeneration.current === generation) setStatus("unauthenticated");
      });
    return () => {
      if (authGeneration.current === generation) authGeneration.current += 1;
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const generation = ++authGeneration.current;
      setError(null);
      try {
        const tokens = await api.auth.login(email, password);
        if (authGeneration.current !== generation) return;
        setDemoMode(false);
        setIsDemo(false);
        try { sessionStorage.removeItem("meridian-demo"); } catch {}
        setAuthToken(tokens.access_token);
        setStatus("authenticated");
        router.push("/");
      } catch (err) {
        if (authGeneration.current !== generation) return;
        setError(err instanceof ApiError ? err.message : "Unable to sign in.");
        throw err;
      }
    },
    [router],
  );

  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      const generation = ++authGeneration.current;
      setError(null);
      try {
        const tokens = await api.auth.register(email, password, fullName);
        if (authGeneration.current !== generation) return;
        setDemoMode(false);
        setIsDemo(false);
        try { sessionStorage.removeItem("meridian-demo"); } catch {}
        setAuthToken(tokens.access_token);
        setStatus("authenticated");
        router.push("/onboarding");
      } catch (err) {
        if (authGeneration.current !== generation) return;
        setError(err instanceof ApiError ? err.message : "Unable to create account.");
        throw err;
      }
    },
    [router],
  );

  const value = useMemo(
    () => ({ status, error, login, register, logout, isDemo, toggleDemo }),
    [status, error, login, register, logout, isDemo, toggleDemo],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
