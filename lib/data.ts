// Shared display types + formatting utilities for the Meridian frontend.
//
// This module used to also export static mock data arrays. Those have been
// removed — real data now comes from the backend via lib/data-provider.tsx,
// which fetches from the API and maps responses onto the types below. Every
// leaf component keeps importing its type from here; only the *value*
// import changed (a hook from lib/data-provider instead of a const here).

export function formatCurrency(
  value: number,
  opts?: { compact?: boolean; sign?: boolean },
) {
  const { compact, sign } = opts ?? {};
  const abs = Math.abs(value);
  const prefix = sign && value > 0 ? "+" : value < 0 ? "-" : "";
  if (compact && abs >= 1000) {
    const units = [
      { v: 1e9, s: "B" },
      { v: 1e6, s: "M" },
      { v: 1e3, s: "K" },
    ];
    for (const u of units) {
      if (abs >= u.v) {
        return `${prefix}$${(abs / u.v).toFixed(abs / u.v >= 100 ? 0 : 1)}${u.s}`;
      }
    }
  }
  return `${prefix}$${abs.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function formatPercent(
  value: number,
  opts?: { sign?: boolean; digits?: number },
) {
  const { sign, digits = 1 } = opts ?? {};
  const prefix = sign && value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(digits)}%`;
}

export type Kpi = {
  id: string;
  label: string;
  value: string;
  raw: number;
  // Day-over-day delta/trend/sparkline data would require a balance-history
  // table the backend doesn't have. Rather than fabricate a plausible-looking
  // trend, these are optional and simply omitted when there's no real data
  // to back them (see HANDOFF.md "Decisions made").
  delta?: number;
  deltaLabel?: string;
  trend?: "up" | "down";
  spark?: number[];
  hint: string;
};

export type NetWorthPoint = {
  month: string;
  assets: number;
  liabilities: number;
  net: number;
  projected?: boolean;
};

export type AllocationSlice = {
  name: string;
  value: number;
  amount: number;
  color: string;
};

export type CashflowPoint = {
  month: string;
  income: number;
  expenses: number;
};

export type Account = {
  id: string;
  name: string;
  // No institution-name backing data is guaranteed for every account
  // (manual accounts have none), so this is optional rather than a
  // guessed placeholder.
  institution?: string;
  type:
    | "Investment"
    | "Depository"
    | "Retirement"
    | "Credit"
    | "Loan"
    | "Property";
  mask: string;
  balance: number;
  // No balance-history table exists yet, so day-over-day % change is
  // optional and omitted rather than fabricated (see HANDOFF.md).
  change?: number;
  apy?: number;
  status: "connected" | "attention" | "manual";
  updated: string;
};

export type Transaction = {
  id: string;
  date: string;
  merchant: string;
  category: string;
  account: string;
  amount: number;
  status: "cleared" | "pending";
};

export type Milestone = {
  id: string;
  year: string;
  age?: number;
  title: string;
  // Goal has no `detail` field in the backend schema yet — optional rather
  // than invented.
  detail?: string;
  amount: string;
  status: "done" | "active" | "upcoming";
};

export type Recommendation = {
  id: string;
  title: string;
  body: string;
  impact: string;
  impactValue: number;
  effort: "Low" | "Medium" | "High";
  category: string;
  confidence: number;
};

export type Scenario = {
  id: string;
  name: string;
  description: string;
  netWorthAt65: number;
  // Monthly sustainable withdrawal from retirement accounts, assuming the
  // plan's life-expectancy assumption (95 by default) — i.e. "monthly
  // retirement income", not to be confused with total net worth above.
  monthlyIncomeAtLifeExpectancy: number;
  retirementAge: number;
  monthlyContribution: number;
  successRate: number;
  color: string;
  // Real per-year trajectory from the latest persisted SimulationRun (in
  // millions), aligned 1:1 with `years`. Empty until a run exists.
  series: number[];
  years: string[];
};

export type Insight = {
  id: string;
  kind: "observation" | "alert" | "opportunity";
  text: string;
  meta: string;
};

export type FinancialHealth = {
  overall: number;
  liquidity: number;
  diversification: number;
  debtRatio: number;
  savingsDiscipline: number;
};
