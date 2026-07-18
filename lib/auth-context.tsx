"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, setAuthToken, setUnauthorizedHandler } from "@/lib/api-client";

const ACCESS_TOKEN_KEY = "meridian.access_token";
const REFRESH_TOKEN_KEY = "meridian.refresh_token";

type AuthState = {
  status: "loading" | "authenticated" | "unauthenticated";
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [status, setStatus] = useState<AuthState["status"]>("loading");
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setAuthToken(null);
    setStatus("unauthenticated");
    router.push("/login");
  }, [router]);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  // Hydrate from localStorage on first mount.
  useEffect(() => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (token) {
      setAuthToken(token);
      setStatus("authenticated");
    } else {
      setStatus("unauthenticated");
    }
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      setError(null);
      try {
        const tokens = await api.auth.login(email, password);
        localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
        localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
        setAuthToken(tokens.access_token);
        setStatus("authenticated");
        router.push("/");
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Unable to sign in.");
        throw err;
      }
    },
    [router],
  );

  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      setError(null);
      try {
        const tokens = await api.auth.register(email, password, fullName);
        localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
        localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
        setAuthToken(tokens.access_token);
        setStatus("authenticated");
        router.push("/onboarding");
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Unable to create account.");
        throw err;
      }
    },
    [router],
  );

  const value = useMemo(
    () => ({ status, error, login, register, logout }),
    [status, error, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
