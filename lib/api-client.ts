// Typed client for the Meridian FastAPI backend. This is the single place
// that knows the backend's response shapes; lib/data-provider.tsx maps
// these onto the display types in lib/data.ts.

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

let authToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

/** Called once by AuthProvider so the client always has the latest token. */
export function setAuthToken(token: string | null) {
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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);

  const res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    onUnauthorized?.();
    throw new ApiError(401, "Session expired. Please sign in again.");
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // response wasn't JSON; fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
const patch = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "PATCH",
    body: body ? JSON.stringify(body) : undefined,
  });

// ---------------------------------------------------------------------------
// Backend response/request shapes (mirrors app/schemas/*.py exactly)
// ---------------------------------------------------------------------------

export type ApiTokenResponse = { access_token: string; refresh_token: string };

export type ApiUser = {
  id: string;
  email: string;
  full_name: string;
  base_currency: string;
  date_of_birth: string | null;
};

export type ApiPlanningProfile = {
  target_retirement_age: number;
  target_equity_allocation: string;
  default_withdrawal_rate: string;
  include_social_security: boolean;
  expected_return: string;
  inflation_rate: string;
};

export type ApiAccount = {
  id: string;
  name: string;
  type:
    | "investment"
    | "depository"
    | "retirement"
    | "credit"
    | "loan"
    | "property";
  balance: string;
  currency: string;
  mask: string | null;
  apy: string | null;
  status: "connected" | "attention" | "manual";
  institution: string | null;
  updated_at: string | null;
};

export type ApiPlaidLinkToken = { link_token: string; expiration: string };

export type ApiPlaidExchangeResponse = {
  institution: { id: string; name: string; status: string };
  accounts: ApiAccount[];
};

export type ApiAccountList = {
  data: ApiAccount[];
  total_assets: string;
  total_liabilities: string;
  net_worth: string;
};

export type ApiTransaction = {
  id: string;
  account_id: string;
  posted_at: string;
  merchant: string;
  category: string;
  amount: string;
  type: "income" | "expense" | "transfer" | "contribution";
  status: "cleared" | "pending";
};

export type ApiTransactionList = {
  data: ApiTransaction[];
  total: number;
  limit: number;
  offset: number;
};

export type ApiGoal = {
  id: string;
  title: string;
  target_amount: string;
  target_date: string | null;
  target_age: number | null;
  priority: number;
  status: "done" | "active" | "upcoming";
  linked_account_id: string | null;
};

export type ApiRecommendation = {
  id: string;
  title: string;
  body: string;
  category: string;
  impact_value: string;
  effort: "low" | "medium" | "high";
  confidence: number;
  status: "new" | "applied" | "dismissed";
  generated_at: string | null;
};

export type ApiScenario = {
  id: string;
  name: string;
  description: string | null;
  is_baseline: boolean;
  retirement_age: number;
  savings_rate: string;
  monthly_contribution: string;
  expected_return: string;
  inflation_rate: string;
  withdrawal_rate: string;
  created_at: string;
  updated_at: string;
};

export type ApiScenarioRun = {
  id: string;
  scenario_id: string;
  engine_version: string;
  method: string;
  net_worth_at_target_age: string;
  success_rate: string | null;
  trajectory: {
    year: number;
    age: number;
    assets: string;
    liabilities: string;
    net: string;
  }[];
  created_at: string;
};

export type ApiScenarioCompareRow = {
  scenario_id: string;
  name: string;
  net_worth_at_target_age: string | null;
  retirement_age: number;
  monthly_contribution: string;
  success_rate: string | null;
  has_run: boolean;
};

export type ApiInsight = {
  id: string;
  kind: "observation" | "alert" | "opportunity";
  text: string;
  meta: string;
  generated_at: string | null;
};

export type ApiFinancialHealth = {
  overall: number;
  liquidity: number;
  diversification: number;
  debt_ratio: number;
  savings_discipline: number;
  calculated_at: string | null;
};

export type ApiNetWorthSimulation = {
  net_worth_today: string;
  projected_net_worth_at_horizon: string;
  series: {
    year_index: number;
    age: number;
    assets: string;
    liabilities: string;
    net: string;
  }[];
};

export type ApiAllocationAnalysis = {
  total_market_value: string;
  breakdown: { asset_class: string; market_value: string; weight: string }[];
  actual_equity_allocation: string;
  target_equity_allocation: string;
  drift: string;
  is_within_tolerance: boolean;
  rebalance_suggestions: {
    asset_class: string;
    action: string;
    amount: string;
  }[];
};

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const api = {
  auth: {
    register: (email: string, password: string, fullName: string) =>
      post<ApiTokenResponse>("/auth/register", {
        email,
        password,
        full_name: fullName,
      }),
    login: (email: string, password: string) =>
      post<ApiTokenResponse>("/auth/login", { email, password }),
    refresh: (refreshToken: string) =>
      post<ApiTokenResponse>("/auth/refresh", { refresh_token: refreshToken }),
  },
  users: {
    me: () => get<ApiUser>("/users/me"),
    updateMe: (body: {
      full_name?: string;
      base_currency?: string;
      date_of_birth?: string;
    }) => patch<ApiUser>("/users/me", body),
    planningProfile: () =>
      get<ApiPlanningProfile>("/users/me/planning-profile"),
    updatePlanningProfile: (
      body: Partial<{
        target_retirement_age: number;
        target_equity_allocation: string;
        default_withdrawal_rate: string;
        include_social_security: boolean;
        expected_return: string;
        inflation_rate: string;
      }>,
    ) => patch<ApiPlanningProfile>("/users/me/planning-profile", body),
  },
  accounts: {
    list: () => get<ApiAccountList>("/accounts"),
    allocation: () => get<ApiAllocationAnalysis>("/accounts/allocation"),
  },
  plaid: {
    // Never returns or logs anything token-related — the backend keeps the
    // Plaid access_token server-side (encrypted at rest) and this client
    // only ever sees a short-lived link_token / one-time public_token.
    createLinkToken: () => post<ApiPlaidLinkToken>("/plaid/link-token"),
    exchangePublicToken: (publicToken: string) =>
      post<ApiPlaidExchangeResponse>("/plaid/exchange-public-token", {
        public_token: publicToken,
      }),
  },
  transactions: {
    list: (params?: { limit?: number; offset?: number }) => {
      const qs = new URLSearchParams();
      if (params?.limit) qs.set("limit", String(params.limit));
      if (params?.offset) qs.set("offset", String(params.offset));
      const suffix = qs.toString() ? `?${qs}` : "";
      return get<ApiTransactionList>(`/transactions${suffix}`);
    },
  },
  goals: {
    list: () => get<ApiGoal[]>("/goals"),
  },
  scenarios: {
    list: () => get<ApiScenario[]>("/scenarios"),
    create: (body: {
      name: string;
      description?: string;
      current_age: number;
      retirement_age: number;
      monthly_contribution?: string;
    }) => post<ApiScenario>("/scenarios", body),
    runs: (scenarioId: string) =>
      get<{ data: ApiScenarioRun[] }>(`/scenarios/${scenarioId}/runs`),
    run: (
      scenarioId: string,
      body: {
        current_age: number;
        current_retirement_balance: string;
        annual_spending_target?: string;
        include_monte_carlo?: boolean;
        monte_carlo_trials?: number;
      },
    ) => post<ApiScenarioRun>(`/scenarios/${scenarioId}/run`, body),
    compare: (scenarioIds: string[]) =>
      post<{ rows: ApiScenarioCompareRow[] }>("/scenarios/compare", {
        scenario_ids: scenarioIds,
      }),
  },
  simulations: {
    netWorth: (body: {
      current_age: number;
      retirement_age: number;
      years: number;
      expected_return?: string;
      annual_net_contribution?: string;
    }) => post<ApiNetWorthSimulation>("/simulations/net-worth", body),
  },
  recommendations: {
    list: () => get<ApiRecommendation[]>("/recommendations"),
    generate: () => post<ApiRecommendation[]>("/recommendations/generate"),
    update: (id: string, status: "applied" | "dismissed") =>
      patch<ApiRecommendation>(`/recommendations/${id}`, { status }),
  },
  insights: {
    list: () => get<ApiInsight[]>("/insights"),
  },
  financialHealth: {
    get: () => get<ApiFinancialHealth>("/financial-health"),
    recalculate: () =>
      post<ApiFinancialHealth>("/financial-health/recalculate", {}),
  },
};
