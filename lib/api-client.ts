// Typed client for the Meridian FastAPI backend. This is the single place
// that knows the backend's response shapes; lib/data-provider.tsx maps
// these onto the display types in lib/data.ts.

import { del, get, patch, post, put, refreshAccessToken } from "@/lib/api-transport";

export {
  ApiError,
  clearApiCache,
  formatApiErrorDetail,
  setAuthToken,
  setDemoMode,
  setUnauthorizedHandler,
} from "@/lib/api-transport";

// ---------------------------------------------------------------------------
// Backend response/request shapes (mirrors app/schemas/*.py exactly)
// ---------------------------------------------------------------------------

export type ApiTokenResponse = { access_token: string; token_type: string };

export type ApiAgentChatResponse = {
  conversation_id: string;
  reply: string;
  tool_calls: { tool: string; arguments: Record<string, unknown> }[];
  structured_results: { tool: string; result: unknown }[];
};

export type ApiAgentConversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
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
export type ApiLiability = { id: string; account_id: string; principal: string | null; interest_rate: string | null; term_months: number | null; minimum_payment: string | null; origination_date: string | null };
export type ApiLoanBalanceRule = {
  id: string;
  account_id: string;
  mode: "scheduled" | "merchant";
  amount: string | null;
  frequency: "once" | "monthly" | null;
  next_run_date: string | null;
  merchant_pattern: string | null;
  active: boolean;
  created_at: string;
};
export type ApiHolding = { id: string; account_id: string; symbol: string; quantity: string; cost_basis: string; market_value: string; asset_class: "equity" | "fixed_income" | "real_estate" | "cash" | "alternatives"; as_of: string; pricing_mode: "manual" | "automatic"; last_price: string | null };
export type ApiCashFlowOutlook = { series: { month_index: number; income: string; expenses: string; net: string }[]; average_monthly_surplus: string; projected_savings_rate: string; income_source: string; expense_source: string };
export type ApiActivitySummary = { history_start: string | null; months: string[]; month_count: number; period_start: string | null; period_end: string | null; label: string; average_monthly_income: string | null; average_monthly_expenses: string | null; average_monthly_surplus: string | null };
export type ApiDebtPlan = { strategy: "avalanche" | "snowball"; months_to_debt_free: number; total_interest_paid: string; payoff_order: string[]; paid_off: boolean; warning: string | null };

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

/** Account rows returned by the archived-account recovery endpoint. */
export type ApiArchivedAccount = ApiAccount & {
  archived_at: string;
};

export type ApiDisconnectedDataSummary = {
  account_count: number;
  transaction_count: number;
};

export type ApiDisconnectedDataDeleteResponse = ApiDisconnectedDataSummary & {
  deleted: boolean;
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

export type ApiFinancialDataRefreshResponse = {
  institutions: ApiPlaidRefreshInstitution[];
  market: {
    symbols_updated: number;
    holdings_updated: number;
    accounts_updated: number;
    errors: Record<string, string>;
  };
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
  type: "income" | "expense" | "transfer" | "credit_card_payment" | "contribution";
  status: "cleared" | "pending";
  budget_category_id: string | null;
  budget_category_name: string | null;
  ignored_from_budget: boolean;
  account_name: string | null;
  account_archived: boolean;
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
  budget_category_id: string | null;
  budget_category_name: string | null;
  transaction_type: "income" | "transfer" | "credit_card_payment" | null;
  merchant_pattern: string;
};

export type ApiBudgetSummary = {
  daily_spending?: (string | null)[];
  previous_daily_spending?: (string | null)[];
  average_daily_spending?: (string | null)[];
  average_month_count?: number;
  average_period_start?: string | null;
  average_period_end?: string | null;
  history_start?: string | null;
  as_of?: string | null;
  reconciliation?: { cash_flow_expenses: string; excluded_expenses: string; reimbursements: string; categorized_transfer_spending?: string; budget_spending: string; pending: string };
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
  type: ApiTransaction["type"];
  budget_category_id: string | null;
  budget_category_name: string | null;
  ignored_from_budget: boolean;
};

export type ApiTransactionList = {
  totals?: { income: string; spending: string; net_cash_flow: string } | null;
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

export type ApiCsvImportRow = {
  row_number: number;
  posted_at: string;
  merchant: string;
  category: string;
  amount: string;
  type: ApiTransaction["type"];
  likely_duplicate: boolean;
  warnings: string[];
  force_import?: boolean;
};

export type ApiCsvImportPreview = {
  rows: ApiCsvImportRow[];
  importable_count: number;
  duplicate_count: number;
};

export type ApiCsvImportOverride = Omit<ApiCsvImportRow, "likely_duplicate" | "warnings" | "force_import"> & { include: boolean; force_import?: boolean };

export type ApiScenarioPreview = {
  net_worth_at_target_age: string;
  retirement_balance_at_target_age?: string;
  monthly_sustainable_withdrawal: string | null;
  success_rate: string | null;
  trajectory: { year: number; age: number; assets: string; liabilities: string; net: string }[];
  retirement_trajectory: { year: number; age: number; balance: string; withdrawal: string }[];
  model_metadata: { model_version: string; success_metric: string; trials: number; seed: number; percentile_method: string; estimate_disclosure: string; exclusions: string[] } | null;
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
  total_gain_loss: string | null;
  gain_loss_holding_count?: number;
  excluded_gain_loss_value?: string;
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
    cost_basis: string | null;
    market_value: string;
    gain_loss: string | null;
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
    refresh: async (): Promise<ApiTokenResponse> => ({ access_token: await refreshAccessToken(), token_type: "bearer" }),
    logout: () => post<void>("/auth/logout"),
    requestPasswordReset: (email: string) =>
      post<void>("/auth/password-reset/request", { email }),
    confirmPasswordReset: (token: string, password: string) =>
      post<void>("/auth/password-reset/confirm", { token, password }),
  },
  agent: {
    chat: (message: string, conversationId?: string | null) =>
      post<ApiAgentChatResponse>("/agent/chat", {
        message,
        conversation_id: conversationId ?? null,
      }),
    conversations: () => get<ApiAgentConversation[]>("/agent/conversations"),
    conversationMessages: (conversationId: string) =>
      get<ApiAgentMessage[]>(`/agent/conversations/${conversationId}/messages`),
    deleteConversation: (conversationId: string) =>
      del<void>(`/agent/conversations/${conversationId}`),
    history: () => get<ApiAgentMessage[]>("/agent/history"),
    clearHistory: () => del<void>("/agent/history"),
  },
  activity: {
    summary: () => get<ApiActivitySummary>("/activity/summary"),
  },
  users: {
    me: () => get<ApiUser>("/users/me"),
    updateMe: (body: { full_name?: string; base_currency?: "USD"; date_of_birth?: string | null }) =>
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
    update: (accountId: string, body: { name?: string; balance?: string; mask?: string | null; apy?: string | null }) =>
      patch<ApiAccount>(`/accounts/${accountId}`, body),
    rename: (accountId: string, name: string) =>
      patch<ApiAccount>(`/accounts/${accountId}/name`, { name }),
    /** Archive an account; the backend retains its history for recovery. */
    archive: (accountId: string) => del<void>(`/accounts/${accountId}`),
    archived: () => get<ApiArchivedAccount[]>("/accounts/archived"),
    restore: (accountId: string) => post<ApiAccount>(`/accounts/${accountId}/restore`),
    disconnectedImportedDataSummary: () =>
      get<ApiDisconnectedDataSummary>("/accounts/disconnected-imported-data"),
    permanentlyDeleteDisconnectedImportedData: () =>
      del<ApiDisconnectedDataDeleteResponse>("/accounts/disconnected-imported-data"),
    sync: (accountId: string) => post<ApiPlaidRefreshInstitution>(`/accounts/${accountId}/sync`),
    institutions: () => get<ApiInstitution[]>("/accounts/institutions"),
    unlinkInstitution: (institutionId: string) => del(`/accounts/institutions/${institutionId}`),
    allocation: () => get<ApiAllocationAnalysis>("/accounts/allocation"),
    liability: (id: string) => get<ApiLiability | null>(`/accounts/${id}/liability`),
    saveLiability: (id: string, body: Omit<ApiLiability, "id" | "account_id">) =>
      put<ApiLiability>(`/accounts/${id}/liability`, body),
    balanceRules: (id: string) => get<ApiLoanBalanceRule[]>(`/accounts/${id}/balance-rules`),
    createBalanceRule: (id: string, body: { mode: "scheduled" | "merchant"; amount?: string; frequency?: "once" | "monthly"; next_run_date?: string; merchant_pattern?: string }) =>
      post<ApiLoanBalanceRule>(`/accounts/${id}/balance-rules`, body),
    deleteBalanceRule: (accountId: string, ruleId: string) => del<void>(`/accounts/${accountId}/balance-rules/${ruleId}`),
    holdings: (id: string) => get<ApiHolding[]>(`/accounts/${id}/holdings`),
    addHolding: (id: string, body: Omit<ApiHolding, "id" | "account_id" | "last_price">) => post<ApiHolding>(`/accounts/${id}/holdings`, body),
    deleteHolding: (id: string) => del<void>(`/holdings/${id}`),
  },
  investments: {
    dashboard: () => get<ApiInvestmentDashboard>("/investments/dashboard"),
  },
  sync: {
    all: () => post<ApiFinancialDataRefreshResponse>("/sync"),
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
    merchants: (search: string, signal?: AbortSignal) => get<string[]>(`/transactions/merchants?${new URLSearchParams({ search })}`, { signal }),
    delete: (id: string) => del<void>(`/transactions/${id}`),
    update: (id: string, body: Partial<Pick<ApiTransaction, "posted_at" | "merchant" | "category" | "amount" | "type">>) => patch<ApiTransaction>(`/transactions/${id}`, body),
    list: (params?: {
      limit?: number;
      offset?: number;
      accountId?: string;
      category?: string;
      budgetCategoryId?: string;
      direction?: "inflow" | "outflow";
      search?: string;
      merchant?: string;
      since?: string;
      until?: string;
      includeArchived?: boolean;
        cashFlowOnly?: boolean;
        type?: ApiTransaction["type"];
        includeTotals?: boolean;
    }, signal?: AbortSignal) => {
      const qs = new URLSearchParams();
      if (params?.limit) qs.set("limit", String(params.limit));
      if (params?.offset) qs.set("offset", String(params.offset));
      if (params?.accountId) qs.set("account_id", params.accountId);
      if (params?.category) qs.set("category", params.category);
      if (params?.budgetCategoryId) qs.set("budget_category_id", params.budgetCategoryId);
      if (params?.direction) qs.set("direction", params.direction);
      if (params?.search) qs.set("search", params.search);
      if (params?.merchant) qs.set("merchant", params.merchant);
      if (params?.since) qs.set("since", params.since);
      if (params?.until) qs.set("until", params.until);
      if (params?.includeArchived) qs.set("include_archived", "true");
      if (params?.cashFlowOnly) qs.set("cash_flow_only", "true");
      if (params?.type) qs.set("type", params.type);
      if (params?.includeTotals) qs.set("include_totals", "true");
      const suffix = qs.toString() ? `?${qs}` : "";
      return get<ApiTransactionList>(`/transactions${suffix}`, { signal });
    },
    listAll: async (params?: {
      accountId?: string;
      category?: string;
      budgetCategoryId?: string;
      merchant?: string;
      since?: string;
      until?: string;
    }, signal?: AbortSignal) => {
      const pageSize = 200;
      const data: ApiTransaction[] = [];
      let offset = 0;
      let total = Number.POSITIVE_INFINITY;

      while (offset < total) {
        const page = await api.transactions.list({
          ...params,
          limit: pageSize,
          offset,
        }, signal);
        data.push(...page.data);
        total = page.total;
        if (page.data.length === 0) break;
        offset += page.data.length;
      }

      return data;
    },
    updateBudgetCategory: (transactionId: string, budgetCategoryId: string | null, ignoredFromBudget?: boolean) =>
      patch<ApiTransaction>(`/transactions/${transactionId}/budget-category`, {
        budget_category_id: budgetCategoryId,
        ...(ignoredFromBudget === undefined ? {} : { ignored_from_budget: ignoredFromBudget }),
      }),
    markReviewed: (transactionId: string) => post<void>(`/transactions/${transactionId}/review`),
    updateClassification: (transactionId: string, type: ApiTransaction["type"]) =>
      patch<ApiTransaction>(`/transactions/${transactionId}/classification`, { type }),
    create: (body: {
      account_id: string;
      posted_at: string;
      merchant: string;
      category: string;
      amount: string;
      type: ApiTransaction["type"];
      status?: ApiTransaction["status"];
    }) => post<ApiTransaction>("/transactions", body),
    previewCsv: (body: { account_id: string; csv_text: string; since?: string; overrides?: ApiCsvImportOverride[] }) =>
      post<ApiCsvImportPreview>("/transactions/import/csv/preview", body),
    importCsv: (body: { account_id: string; csv_text: string; since?: string; overrides?: ApiCsvImportOverride[] }) =>
      post<{ imported_count: number; skipped_duplicate_count: number; data: ApiTransaction[] }>("/transactions/import/csv", body),
  },
  budgets: {
    categories: (signal?: AbortSignal) => get<ApiBudgetCategory[]>("/budgets/categories", { signal }),
    createCategory: (body: { name: string; group_name: string; monthly_limit: string }) =>
      post<ApiBudgetCategory>("/budgets/categories", body),
    updateCategory: (
      categoryId: string,
      body: Partial<{ name: string; group_name: string; monthly_limit: string; active: boolean }>,
    ) => patch<ApiBudgetCategory>(`/budgets/categories/${categoryId}`, body),
    deleteCategory: (categoryId: string) => del<void>(`/budgets/categories/${categoryId}`),
    merchantRules: () => get<ApiMerchantBudgetRule[]>("/budgets/merchant-rules"),
    createMerchantRule: (body: { budget_category_id?: string; transaction_type?: "income" | "transfer" | "credit_card_payment"; merchant_pattern: string }) =>
      post<ApiMerchantBudgetRule>("/budgets/merchant-rules", body),
    deleteMerchantRule: (ruleId: string) => del(`/budgets/merchant-rules/${ruleId}`),
    summary: (month: string, signal?: AbortSignal) =>
      get<ApiBudgetSummary>(`/budgets/summary?month=${month}-01`, { signal }),
    reviewQueue: (signal?: AbortSignal) =>
      get<ApiUncategorizedBudgetTransaction[]>("/budgets/review-queue", { signal }),
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
      inflation_rate?: string;
      withdrawal_rate?: string;
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
    cashFlow: (months: number) => post<ApiCashFlowOutlook>("/simulations/cash-flow", { months }),
    debtOptimization: (body: { account_ids: string[]; extra_monthly_payment: string; strategy: "avalanche" | "snowball" }) => post<ApiDebtPlan>("/simulations/debt-optimization", body),
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
