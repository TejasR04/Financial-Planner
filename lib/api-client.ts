// Typed client for the Meridian FastAPI backend. This is the single place
// that knows the backend's response shapes; lib/data-provider.tsx maps
// these onto the display types in lib/data.ts.

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

let authToken: string | null = null;
let onUnauthorized: (() => void) | null = null;
let refreshPromise: Promise<string> | null = null;

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

async function request<T>(
  path: string,
  options: RequestInit = {},
  retryAfterRefresh = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  const isAuthEntryPoint = path === "/auth/login" || path === "/auth/register";
  if (res.status === 401 && retryAfterRefresh && !isAuthEntryPoint && path !== "/auth/refresh") {
    try {
      if (!refreshPromise) {
        refreshPromise = request<ApiTokenResponse>(
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
      detail = body?.detail ?? detail;
    } catch {
      // response wasn't JSON; fall back to statusText
    }
    // A failed sign-in is not an expired session. Preserve the backend's
    // intentionally generic credential error instead of logging the user out
    // and replacing it with a misleading message.
    if (res.status === 401 && !isAuthEntryPoint && path !== "/auth/refresh") {
      onUnauthorized?.();
      detail = "Session expired. Please sign in again.";
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
const patch = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined });
const del = <T>(path: string) => request<T>(path, { method: "DELETE" });

// ---------------------------------------------------------------------------
// Backend response/request shapes (mirrors app/schemas/*.py exactly)
// ---------------------------------------------------------------------------

export type ApiTokenResponse = { access_token: string; token_type: string };

export type ApiAgentChatResponse = {
  reply: string;
  tool_calls: { tool: string; arguments: Record<string, unknown> }[];
  structured_results: { tool: string; result: unknown }[];
};

export type ApiAgentMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type ApiUser = {
  id: string;
  email: string;
  full_name: string;
  base_currency: "USD";
  date_of_birth: string | null;
};

export type ApiPlanningProfile = {
  target_retirement_age: number;
  target_equity_allocation: string;
  default_withdrawal_rate: string;
  include_social_security: boolean;
  expected_return: string;
  inflation_rate: string;
  target_savings_rate: string | null;
  cash_reserve_target: string | null;
};

export type ApiIncomeSource = { id: string; name: string; annual_amount: string; growth_rate: string; active: boolean };
export type ApiLiability = { id: string; account_id: string; principal: string; interest_rate: string; term_months: number; minimum_payment: string; origination_date: string };
export type ApiHolding = { id: string; account_id: string; symbol: string; quantity: string; cost_basis: string; market_value: string; asset_class: "equity" | "fixed_income" | "real_estate" | "cash" | "alternatives"; as_of: string };

export type ApiAccount = {
  id: string;
  name: string;
  type: "investment" | "depository" | "retirement" | "credit" | "loan" | "property";
  balance: string;
  currency: "USD";
  mask: string | null;
  apy: string | null;
  status: "connected" | "attention" | "manual";
  institution: string | null;
  institution_id: string | null;
  institution_status: "healthy" | "action_required" | "error" | null;
  institution_last_synced_at: string | null;
  updated_at: string | null;
};

export type ApiInstitution = {
  id: string;
  name: string;
  provider: "plaid" | "manual" | "csv";
  status: "healthy" | "action_required" | "error";
  last_synced_at: string | null;
  account_count: number;
};

export type ApiPlaidLinkToken = { link_token: string; expiration: string };

export type ApiPlaidExchangeResponse = {
  institution: { id: string; name: string; status: string };
  accounts: ApiAccount[];
};

export type ApiPlaidRefreshInstitution = {
  institution_id: string;
  institution_name: string;
  status: "healthy" | "error";
  accounts_synced: number;
  transactions_created: number;
  transactions_updated: number;
  transactions_removed: number;
  holdings_synced: number;
  error: string | null;
};

export type ApiPlaidRefreshResponse = {
  data: ApiPlaidRefreshInstitution[];
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
  budget_category_id: string | null;
};

export type ApiBudgetCategory = {
  id: string;
  name: string;
  group_name: string;
  monthly_limit: string;
  sort_order: number;
  active: boolean;
};

export type ApiMerchantBudgetRule = {
  id: string;
  budget_category_id: string;
  budget_category_name: string;
  merchant_pattern: string;
};

export type ApiBudgetSummary = {
  month: string;
  categories: {
    budget_category_id: string;
    name: string;
    group_name: string;
    budgeted: string;
    spent: string;
    pending: string;
    remaining: string;
    forecast: string;
  }[];
  uncategorized: { spent: string; pending: string; transaction_count: number };
};

export type ApiUncategorizedBudgetTransaction = {
  id: string;
  posted_at: string;
  merchant: string;
  provider_category: string;
  amount: string;
  status: "cleared" | "pending";
};

export type ApiTransactionList = {
  data: ApiTransaction[];
  total: number;
  limit: number;
  offset: number;
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
  desired_monthly_income_today: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiScenarioRun = {
  id: string;
  scenario_id: string;
  engine_version: string;
  method: string;
  net_worth_at_target_age: string;
  monthly_sustainable_withdrawal: string | null;
  success_rate: string | null;
  trajectory: { year: number; age: number; assets: string; liabilities: string; net: string }[];
  retirement_trajectory: { year: number; age: number; balance: string; withdrawal?: string }[] | null;
  created_at: string;
};

export type ApiScenarioPreview = {
  net_worth_at_target_age: string;
  monthly_sustainable_withdrawal: string | null;
  success_rate: string | null;
  trajectory: { year: number; age: number; assets: string; liabilities: string; net: string }[];
  retirement_trajectory: { year: number; age: number; balance: string; withdrawal: string }[];
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
  series: { year_index: number; age: number; assets: string; liabilities: string; net: string }[];
};

export type ApiRetirementSimulation = {
  projected_balance_at_retirement: string;
  annual_sustainable_withdrawal: string;
  monthly_sustainable_withdrawal: string;
  is_feasible: boolean;
  shortfall_or_surplus: string;
  years_to_retirement: number;
};

export type ApiAllocationAnalysis = {
  total_market_value: string;
  breakdown: { asset_class: string; market_value: string; weight: string }[];
  actual_equity_allocation: string;
  target_equity_allocation: string;
  drift: string;
  is_within_tolerance: boolean;
  rebalance_suggestions: { asset_class: string; action: string; amount: string }[];
};

export type ApiInvestmentDashboard = {
  total_value: string;
  total_holdings_value: string;
  total_cost_basis: string;
  total_gain_loss: string;
  account_count: number;
  holding_count: number;
  accounts: {
    id: string;
    name: string;
    type: "investment" | "retirement";
    balance: string;
    institution: string | null;
    updated_at: string | null;
  }[];
  holdings: {
    account_id: string;
    account_name: string;
    symbol: string;
    quantity: string;
    cost_basis: string;
    market_value: string;
    gain_loss: string;
    asset_class: string;
    as_of: string;
  }[];
  allocation: { asset_class: string; market_value: string; weight: string }[];
  history: { date: string; value: string }[];
};

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const api = {
  auth: {
    register: (email: string, password: string, fullName: string) =>
      post<ApiTokenResponse>("/auth/register", { email, password, full_name: fullName }),
    login: (email: string, password: string) =>
      post<ApiTokenResponse>("/auth/login", { email, password }),
    refresh: () => post<ApiTokenResponse>("/auth/refresh"),
    logout: () => post<void>("/auth/logout"),
    requestPasswordReset: (email: string) =>
      post<void>("/auth/password-reset/request", { email }),
    confirmPasswordReset: (token: string, password: string) =>
      post<void>("/auth/password-reset/confirm", { token, password }),
  },
  agent: {
    chat: (message: string) =>
      post<ApiAgentChatResponse>("/agent/chat", { message }),
    history: () => get<ApiAgentMessage[]>("/agent/history"),
    clearHistory: () => del<void>("/agent/history"),
  },
  users: {
    me: () => get<ApiUser>("/users/me"),
    updateMe: (body: { full_name?: string; base_currency?: "USD"; date_of_birth?: string }) =>
      patch<ApiUser>("/users/me", body),
    planningProfile: () => get<ApiPlanningProfile>("/users/me/planning-profile"),
    updatePlanningProfile: (body: Partial<{
      target_retirement_age: number;
      target_equity_allocation: string;
      default_withdrawal_rate: string;
      include_social_security: boolean;
      expected_return: string;
      inflation_rate: string;
      target_savings_rate: string | null;
      cash_reserve_target: string | null;
    }>) => patch<ApiPlanningProfile>("/users/me/planning-profile", body),
  },
  incomeSources: {
    list: () => get<ApiIncomeSource[]>("/income-sources"),
    create: (body: { name: string; annual_amount: string; growth_rate: string; active?: boolean }) => post<ApiIncomeSource>("/income-sources", body),
    update: (id: string, body: Partial<{ name: string; annual_amount: string; growth_rate: string; active: boolean }>) => patch<ApiIncomeSource>(`/income-sources/${id}`, body),
    delete: (id: string) => del<void>(`/income-sources/${id}`),
  },
  accounts: {
    list: (params?: { type?: ApiAccount["type"] }) => {
      const suffix = params?.type ? `?type=${params.type}` : "";
      return get<ApiAccountList>(`/accounts${suffix}`);
    },
    create: (body: {
      name: string;
      type: ApiAccount["type"];
      balance: string;
      mask?: string;
      apy?: string;
    }) => post<ApiAccount>("/accounts", body),
    update: (accountId: string, body: { name?: string; balance?: string; mask?: string; apy?: string }) =>
      patch<ApiAccount>(`/accounts/${accountId}`, body),
    delete: (accountId: string) => del(`/accounts/${accountId}`),
    sync: (accountId: string) => post<ApiPlaidRefreshInstitution>(`/accounts/${accountId}/sync`),
    institutions: () => get<ApiInstitution[]>("/accounts/institutions"),
    unlinkInstitution: (institutionId: string) => del(`/accounts/institutions/${institutionId}`),
    allocation: () => get<ApiAllocationAnalysis>("/accounts/allocation"),
    liability: (id: string) => get<ApiLiability | null>(`/accounts/${id}/liability`),
    saveLiability: (id: string, body: Omit<ApiLiability, "id" | "account_id">) => request<ApiLiability>(`/accounts/${id}/liability`, { method: "PUT", body: JSON.stringify(body) }),
    holdings: (id: string) => get<ApiHolding[]>(`/accounts/${id}/holdings`),
    addHolding: (id: string, body: Omit<ApiHolding, "id" | "account_id">) => post<ApiHolding>(`/accounts/${id}/holdings`, body),
    deleteHolding: (id: string) => del<void>(`/holdings/${id}`),
  },
  investments: {
    dashboard: () => get<ApiInvestmentDashboard>("/investments/dashboard"),
  },
  plaid: {
    // Never returns or logs anything token-related — the backend keeps the
    // Plaid access_token server-side (encrypted at rest) and this client
    // only ever sees a short-lived link_token / one-time public_token.
    createLinkToken: (institutionId?: string) =>
      post<ApiPlaidLinkToken>(
        "/plaid/link-token",
        institutionId ? { institution_id: institutionId } : undefined,
      ),
    exchangePublicToken: (publicToken: string) =>
      post<ApiPlaidExchangeResponse>("/plaid/exchange-public-token", { public_token: publicToken }),
    refresh: () => post<ApiPlaidRefreshResponse>("/plaid/refresh"),
  },
  transactions: {
    list: (params?: {
      limit?: number;
      offset?: number;
      accountId?: string;
      category?: string;
      since?: string;
      until?: string;
    }) => {
      const qs = new URLSearchParams();
      if (params?.limit) qs.set("limit", String(params.limit));
      if (params?.offset) qs.set("offset", String(params.offset));
      if (params?.accountId) qs.set("account_id", params.accountId);
      if (params?.category) qs.set("category", params.category);
      if (params?.since) qs.set("since", params.since);
      if (params?.until) qs.set("until", params.until);
      const suffix = qs.toString() ? `?${qs}` : "";
      return get<ApiTransactionList>(`/transactions${suffix}`);
    },
    updateBudgetCategory: (transactionId: string, budgetCategoryId: string | null) =>
      patch<ApiTransaction>(`/transactions/${transactionId}/budget-category`, {
        budget_category_id: budgetCategoryId,
      }),
    create: (body: {
      account_id: string;
      posted_at: string;
      merchant: string;
      category: string;
      amount: string;
      type: ApiTransaction["type"];
      status?: ApiTransaction["status"];
    }) => post<ApiTransaction>("/transactions", body),
    importCsv: (body: { account_id: string; csv_text: string; since?: string }) =>
      post<{ imported_count: number; data: ApiTransaction[] }>("/transactions/import/csv", body),
  },
  budgets: {
    categories: () => get<ApiBudgetCategory[]>("/budgets/categories"),
    createCategory: (body: { name: string; group_name: string; monthly_limit: string }) =>
      post<ApiBudgetCategory>("/budgets/categories", body),
    updateCategory: (
      categoryId: string,
      body: Partial<{ name: string; group_name: string; monthly_limit: string; active: boolean }>,
    ) => patch<ApiBudgetCategory>(`/budgets/categories/${categoryId}`, body),
    merchantRules: () => get<ApiMerchantBudgetRule[]>("/budgets/merchant-rules"),
    createMerchantRule: (body: { budget_category_id: string; merchant_pattern: string }) =>
      post<ApiMerchantBudgetRule>("/budgets/merchant-rules", body),
    deleteMerchantRule: (ruleId: string) => del(`/budgets/merchant-rules/${ruleId}`),
    summary: (month: string) => get<ApiBudgetSummary>(`/budgets/summary?month=${month}-01`),
    uncategorized: (month: string) =>
      get<ApiUncategorizedBudgetTransaction[]>(`/budgets/uncategorized?month=${month}-01`),
  },
  scenarios: {
    list: () => get<ApiScenario[]>("/scenarios"),
    create: (body: {
      name: string;
      description?: string;
      current_age: number;
      retirement_age: number;
      monthly_contribution?: string;
      expected_return?: string;
      desired_monthly_income_today?: string;
    }) => post<ApiScenario>("/scenarios", body),
    update: (
      scenarioId: string,
      body: Partial<{
        name: string;
        description: string;
        retirement_age: number;
        monthly_contribution: string;
        expected_return: string;
        savings_rate: string;
        inflation_rate: string;
        withdrawal_rate: string;
        desired_monthly_income_today: string;
        clear_income_target: boolean;
      }>,
    ) => patch<ApiScenario>(`/scenarios/${scenarioId}`, body),
    delete: (scenarioId: string) => del(`/scenarios/${scenarioId}`),
    duplicate: (scenarioId: string) => post<ApiScenario>(`/scenarios/${scenarioId}/duplicate`),
    sensitivity: (
      scenarioId: string,
      body: { current_age: number; current_retirement_balance: string },
    ) =>
      post<{
        baseline_balance_at_retirement: string;
        baseline_success_rate: string | null;
        rows: { label: string; kind: string; value: string; note: string }[];
      }>(`/scenarios/${scenarioId}/sensitivity`, body),
    runs: (scenarioId: string) => get<{ data: ApiScenarioRun[] }>(`/scenarios/${scenarioId}/runs`),
    preview: (
      scenarioId: string,
      body: {
        current_age: number;
        current_retirement_balance: string;
        annual_spending_target?: string;
        include_monte_carlo?: boolean;
        monte_carlo_trials?: number;
      },
    ) => post<ApiScenarioPreview>(`/scenarios/${scenarioId}/preview`, body),
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
      post<{ rows: ApiScenarioCompareRow[] }>("/scenarios/compare", { scenario_ids: scenarioIds }),
  },
  simulations: {
    retirement: (body: {
      current_age: number;
      retirement_age: number;
      current_retirement_balance: string;
      annual_contribution: string;
      expected_return?: string;
      inflation_rate?: string;
      withdrawal_rate?: string;
    }) => post<ApiRetirementSimulation>("/simulations/retirement", body),
    netWorth: (body: {
      current_age: number;
      retirement_age: number;
      years: number;
      expected_return?: string;
      annual_net_contribution?: string;
    }) => post<ApiNetWorthSimulation>("/simulations/net-worth", body),
  },
  recommendations: {
    list: (status?: ApiRecommendation["status"]) =>
      get<ApiRecommendation[]>(`/recommendations${status ? `?status=${status}` : ""}`),
    generate: () => post<ApiRecommendation[]>("/recommendations/generate"),
    update: (id: string, status: "applied" | "dismissed") =>
      patch<ApiRecommendation>(`/recommendations/${id}`, { status }),
  },
  insights: {
    list: () => get<ApiInsight[]>("/insights"),
    generate: () => post<ApiInsight[]>("/insights/generate"),
  },
  financialHealth: {
    get: () => get<ApiFinancialHealth>("/financial-health"),
    recalculate: () => post<ApiFinancialHealth>("/financial-health/recalculate", {}),
  },
};
