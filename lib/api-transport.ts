import { demoRequest, resetDemoData } from "@/lib/demo-api";
import { ResponseCache } from "@/lib/response-cache";

const responseCache = new ResponseCache();
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

let demoMode = false;
let dataGeneration = 0;
let authToken: string | null = null;
let onUnauthorized: (() => void) | null = null;
let refreshPromise: Promise<string> | null = null;

type TokenResponse = { access_token: string };
type ValidationDetail = { loc?: unknown[]; msg?: string };

export function clearApiCache() {
  responseCache.clear();
}

export function setDemoMode(enabled: boolean) {
  dataGeneration++;
  demoMode = enabled;
  clearApiCache();
  resetDemoData();
}

/** Called once by AuthProvider so the client always has the latest token. */
export function setAuthToken(token: string | null) {
  if (token !== authToken || token === null) clearApiCache();
  authToken = token;
}

/** Called once by AuthProvider so a 401 can trigger a clean logout. */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function formatApiErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item: ValidationDetail) => {
      if (!item || typeof item.msg !== "string") return [];
      const field = Array.isArray(item.loc)
        ? item.loc.filter((part) => part !== "body").at(-1)
        : undefined;
      const label = typeof field === "string" ? field.replaceAll("_", " ") : "Field";
      return [`${label}: ${item.msg}`];
    });
    if (messages.length) return messages.join("; ");
  }
  return fallback;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retryAfterRefresh = true,
): Promise<T> {
  if (demoMode && !path.startsWith("/auth/")) {
    if (options.method && options.method !== "GET") clearApiCache();
    return structuredClone(demoRequest(path, options)) as T;
  }
  const generation = dataGeneration;
  const mutates = options.method && options.method !== "GET" &&
    !path.startsWith("/simulations/") && !path.endsWith("/preview") && path !== "/scenarios/compare";
  if (mutates) clearApiCache();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });
  if (!path.startsWith("/auth/") && generation !== dataGeneration) {
    throw new ApiError(409, "Data mode changed.");
  }
  if (mutates) clearApiCache();

  const isAuthEntryPoint = path === "/auth/login" || path === "/auth/register";
  if (res.status === 401 && retryAfterRefresh && !isAuthEntryPoint && path !== "/auth/refresh") {
    try {
      if (!refreshPromise) {
        refreshPromise = request<TokenResponse>(
          "/auth/refresh",
          { method: "POST" },
          false,
        ).then((tokens) => {
          setAuthToken(tokens.access_token);
          return tokens.access_token;
        }).finally(() => {
          refreshPromise = null;
        });
      }
      await refreshPromise;
      return request<T>(path, options, false);
    } catch {
      setAuthToken(null);
      onUnauthorized?.();
      throw new ApiError(401, "Session expired. Please sign in again.");
    }
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = formatApiErrorDetail(body?.detail, detail);
    } catch {
      // Response was not JSON; fall back to statusText.
    }
    if (res.status === 401 && !isAuthEntryPoint && path !== "/auth/refresh") {
      onUnauthorized?.();
      detail = "Session expired. Please sign in again.";
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const get = <T>(path: string, options?: RequestInit) =>
  /^\/(accounts|institutions|transactions|budgets)(\/|\?|$)/.test(path)
    ? responseCache.load(path, () => request<T>(path, options), options?.signal)
    : request<T>(path, options);

export const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });

export const patch = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined });

export const put = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined });

export const del = <T>(path: string) => request<T>(path, { method: "DELETE" });
