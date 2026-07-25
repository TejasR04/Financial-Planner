"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useAuth } from "@/lib/auth-context";
import { api, type ApiAccount, type ApiScenarioRun, type ApiTransaction } from "@/lib/api-client";
import {
  formatCurrency,
  type Account,
  type AllocationSlice,
  type CashflowPoint,
  type FinancialHealth,
  type Insight,
  type Institution,
  type Kpi,
  type Milestone,
  type NetWorthPoint,
  type Recommendation,
  type Scenario,
  type Transaction,
} from "@/lib/data";

// ---------------------------------------------------------------------------
// Small formatting helpers local to the mapping layer below.
// ---------------------------------------------------------------------------

function ageFromBirthDate(dob: string | null): number {
  if (!dob) return 35; // no birth date on file yet — a reasonable planning default
  const birth = new Date(dob);
  const now = new Date();
  let age = now.getFullYear() - birth.getFullYear();
  const hadBirthday =
    now.getMonth() > birth.getMonth() ||
    (now.getMonth() === birth.getMonth() && now.getDate() >= birth.getDate());
  if (!hadBirthday) age -= 1;
  return age;
}

function formatRelativeTime(iso: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const diffMs = Date.now() - then;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatShortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function monthKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function twelveMonthWindow(today = new Date()) {
  const start = new Date(today.getFullYear(), today.getMonth() - 11, 1);
  const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
  return {
    start,
    startDate: `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, "0")}-01`,
    end,
  };
}

function buildCashflowSeries(transactions: ApiTransaction[], start: Date, end: Date): CashflowPoint[] {
  const buckets = new Map<string, { income: number; expenses: number }>();
  const cursor = new Date(start.getFullYear(), start.getMonth(), 1);
  while (cursor <= end) {
    buckets.set(monthKey(cursor), { income: 0, expenses: 0 });
    cursor.setMonth(cursor.getMonth() + 1);
  }

  for (const transaction of transactions) {
    const posted = new Date(`${transaction.posted_at}T00:00:00`);
    const bucket = buckets.get(monthKey(posted));
    if (!bucket) continue;
    const amount = Math.abs(parseFloat(transaction.amount));
    if (transaction.type === "income") bucket.income += amount;
    if (transaction.type === "expense") bucket.expenses += amount;
  }

  return Array.from(buckets.entries()).map(([key, value]) => {
    const [year, month] = key.split("-");
    return {
      month: new Date(Number(year), Number(month) - 1, 1).toLocaleDateString("en-US", { month: "short" }),
      income: value.income,
      expenses: value.expenses,
    };
  });
}

const ACCOUNT_TYPE_LABEL: Record<ApiAccount["type"], Account["type"]> = {
  investment: "Investment",
  depository: "Depository",
  retirement: "Retirement",
  credit: "Credit",
  loan: "Loan",
  property: "Property",
};

const ASSET_CLASS_LABEL: Record<string, string> = {
  equity: "Equities",
  fixed_income: "Fixed Income",
  real_estate: "Real Estate",
  cash: "Cash",
  alternatives: "Alternatives",
};

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

// ---------------------------------------------------------------------------
// Shape held in context — already mapped onto the display types in lib/data.
// ---------------------------------------------------------------------------

type AllocationMeta = {
  targetEquityPercent: number;
  driftPercent: number;
  isWithinTolerance: boolean;
};

type ProfileSummary = {
  currentAge: number;
  currentRetirementBalance: number;
  netWorthToday: number;
  targetRetirementAge: number;
  expectedReturn: string; // decimal string, e.g. "0.065" — as the API expects
  monthlySurplusEstimate: number;
};

type UserAccountDetails = {
  fullName: string;
  email: string;
  baseCurrency: string;
  dateOfBirth: string | null;
  targetRetirementAge: number;
  targetEquityAllocation: number; // 0-1 fraction, as the API expects
  defaultWithdrawalRate: number; // 0-1 fraction
  includeSocialSecurity: boolean;
};

type DataState = {
  kpis: Kpi[];
  netWorthSeries: NetWorthPoint[];
  allocation: AllocationSlice[];
  allocationMeta: AllocationMeta | null;
  cashflowSeries: CashflowPoint[];
  accounts: Account[];
  institutions: Institution[];
  transactions: Transaction[];
  milestones: Milestone[];
  recommendations: Recommendation[];
  scenarios: Scenario[];
  insights: Insight[];
  financialHealth: FinancialHealth | null;
  profile: ProfileSummary | null;
  userAccount: UserAccountDetails | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
};

const DataContext = createContext<DataState | null>(null);

const emptyState: Omit<DataState, "loading" | "error" | "refresh"> = {
  kpis: [],
  netWorthSeries: [],
  allocation: [],
  allocationMeta: null,
  cashflowSeries: [],
  accounts: [],
  institutions: [],
  transactions: [],
  milestones: [],
  recommendations: [],
  scenarios: [],
  insights: [],
  financialHealth: null,
  profile: null,
  userAccount: null,
};

export function DataProvider({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const [state, setState] = useState(emptyState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  const refresh = useCallback(() => setRefreshTick((t) => t + 1), []);

  useEffect(() => {
    if (status !== "authenticated") return;
    let cancelled = false;

    async function loadAll() {
      setLoading(true);
      setError(null);
      try {
        const warnings: string[] = [];
        const optional = async <T,>(label: string, request: Promise<T>, fallback: T, report = true): Promise<T> => {
          try {
            return await request;
          } catch {
            if (report) warnings.push(label);
            return fallback;
          }
        };
        const [
          user,
          planningProfile,
          accountList,
          institutionRows,
          transactionList,
          goals,
          scenarioRows,
          recommendationRows,
          health,
          allocationAnalysis,
        ] = await Promise.all([
          api.users.me(),
          api.users.planningProfile(),
          api.accounts.list(),
          optional("institutions", api.accounts.institutions(), []),
          optional("recent transactions", api.transactions.list({ limit: 1000, since: twelveMonthWindow().startDate }), { data: [], total: 0, limit: 1000, offset: 0 }),
          optional("goals", api.goals.list(), []),
          optional("scenarios", api.scenarios.list(), []),
          optional("recommendations", api.recommendations.list(), []),
          optional("financial health", api.financialHealth.get(), null, false),
          optional("allocation", api.accounts.allocation(), null),
        ]);
        const insightRows = await optional("insights", api.insights.list(), []);

        const currentAge = ageFromBirthDate(user.date_of_birth);
        const currentYear = new Date().getFullYear();

        // --- accounts -------------------------------------------------
        const accounts: Account[] = accountList.data.map((a) => ({
          id: a.id,
          name: a.name,
          institution: a.institution ?? undefined,
          institutionId: a.institution_id ?? undefined,
          institutionStatus: a.institution_status ?? undefined,
          type: ACCOUNT_TYPE_LABEL[a.type],
          mask: a.mask ?? "—",
          balance: parseFloat(a.balance),
          apy: a.apy != null ? parseFloat(a.apy) : undefined,
          status: a.institution_status === "error" || a.institution_status === "action_required" ? "attention" : a.status,
          updated: formatRelativeTime(a.institution_last_synced_at ?? a.updated_at),
        }));
        const institutions: Institution[] = institutionRows.map((institution) => ({
          id: institution.id,
          name: institution.name,
          provider: institution.provider,
          status: institution.status,
          lastSyncedAt: institution.last_synced_at,
          accountCount: institution.account_count,
        }));
        const accountNameById = new Map(accountList.data.map((a) => [a.id, a.name]));

        const window = twelveMonthWindow();

        // --- transactions + cashflow -----------------------------------
        const transactions: Transaction[] = transactionList.data.map((t) => ({
          id: t.id,
          postedAt: t.posted_at,
          date: formatShortDate(t.posted_at),
          merchant: t.merchant,
          category: t.category,
          account: accountNameById.get(t.account_id) ?? "Account",
          amount: parseFloat(t.amount),
          type: t.type,
          status: t.status,
        }));
        const cashflowSeries = buildCashflowSeries(transactionList.data, window.start, window.end);
        const averageMonthlyIncome = cashflowSeries.reduce((sum, month) => sum + month.income, 0) / cashflowSeries.length;
        const averageMonthlyExpenses = cashflowSeries.reduce((sum, month) => sum + month.expenses, 0) / cashflowSeries.length;
        const averageMonthlySurplus = averageMonthlyIncome - averageMonthlyExpenses;

        // --- kpis (all values are based on the selected trailing window)
        const netWorthToday = parseFloat(accountList.net_worth);
        const cashHoldings = (allocationAnalysis?.breakdown ?? [])
          .filter((item) => item.asset_class === "cash")
          .reduce((sum, item) => sum + parseFloat(item.market_value), 0);
        const liquidAssets = accountList.data
          .filter((a) => a.type === "depository")
          .reduce((s, a) => s + parseFloat(a.balance), 0) + cashHoldings;
        const savingsRate = averageMonthlyIncome > 0 ? (averageMonthlySurplus / averageMonthlyIncome) * 100 : null;
        const kpis: Kpi[] = [
          {
            id: "net-worth",
            label: "Net Worth",
            value: formatCurrency(netWorthToday),
            raw: netWorthToday,
            hint: "Assets minus liabilities across all linked accounts",
          },
          {
            id: "liquid",
            label: "Liquid Assets",
            value: formatCurrency(liquidAssets),
            raw: liquidAssets,
            hint: "Depository balances plus cash-equivalent investment holdings",
          },
          {
            id: "monthly-cash-flow",
            label: "Monthly Cash Flow",
            value: formatCurrency(averageMonthlySurplus, { sign: true }),
            raw: averageMonthlySurplus,
            hint: "Average monthly income less expenses over the last 12 months",
          },
          {
            id: "savings-rate",
            label: "Savings Rate",
            value: savingsRate == null ? "—" : `${savingsRate.toFixed(1)}%`,
            raw: savingsRate ?? 0,
            hint: "Average income retained after expenses over the last 12 months",
          },
        ];

        // --- net worth series: today (real) + forward projection -------
        let netWorthSeries: NetWorthPoint[] = [
          {
            month: "Today",
            assets: parseFloat(accountList.total_assets),
            liabilities: parseFloat(accountList.total_liabilities),
            net: netWorthToday,
          },
        ];
        try {
          const projection = await api.simulations.netWorth({
            current_age: currentAge,
            retirement_age: planningProfile.target_retirement_age,
            years: Math.max(1, planningProfile.target_retirement_age - currentAge),
            expected_return: planningProfile.expected_return,
            annual_net_contribution: String(Math.max(0, averageMonthlySurplus) * 12),
          });
          netWorthSeries = [
            ...netWorthSeries,
            ...projection.series
              .filter((p) => p.year_index > 0)
              .map((p) => ({
                month: String(currentYear + p.year_index),
                assets: parseFloat(p.assets),
                liabilities: parseFloat(p.liabilities),
                net: parseFloat(p.net),
                projected: true,
              })),
          ];
        } catch {
          // projection is best-effort; the "today" point still renders.
        }

        // --- allocation --------------------------------------------------
        const allocation: AllocationSlice[] = (allocationAnalysis?.breakdown ?? []).map(
          (b, i) => ({
            name: ASSET_CLASS_LABEL[b.asset_class] ?? b.asset_class,
            value: Math.round(parseFloat(b.weight) * 1000) / 10,
            amount: parseFloat(b.market_value),
            color: CHART_COLORS[i % CHART_COLORS.length],
          }),
        );
        const allocationMeta: AllocationMeta | null = allocationAnalysis
          ? {
              targetEquityPercent: Math.round(parseFloat(allocationAnalysis.target_equity_allocation) * 1000) / 10,
              driftPercent: Math.round(parseFloat(allocationAnalysis.drift) * 1000) / 10,
              isWithinTolerance: allocationAnalysis.is_within_tolerance,
            }
          : null;

        // --- milestones (from Goals) -------------------------------------
        const milestones: Milestone[] = goals.map((g) => {
          const targetYear = g.target_date
            ? new Date(`${g.target_date}T00:00:00`).getFullYear()
            : g.target_age
              ? currentYear + (g.target_age - currentAge)
              : currentYear;
          return {
            id: g.id,
            year: String(targetYear),
            age: g.target_age ?? undefined,
            title: g.title,
            amount: formatCurrency(parseFloat(g.target_amount), { compact: true }),
            status: g.status,
          };
        });

        // --- recommendations ----------------------------------------------
        const recommendations: Recommendation[] = recommendationRows.map((r) => ({
          id: r.id,
          title: r.title,
          body: r.body,
          impact: `${formatCurrency(parseFloat(r.impact_value), { sign: true })} / yr`,
          impactValue: parseFloat(r.impact_value),
          effort: (r.effort.charAt(0).toUpperCase() + r.effort.slice(1)) as Recommendation["effort"],
          category: r.category,
          confidence: r.confidence,
        }));

        // --- scenarios (fetch/kick off runs so charts have real data) ----
        const retirementBalance = accountList.data
          .filter((a) => a.type === "retirement")
          .reduce((s, a) => s + parseFloat(a.balance), 0);

        const scenarios: Scenario[] = await Promise.all(
          scenarioRows.map(async (s, i) => {
            let run: ApiScenarioRun | null = null;
            try {
              const runHistory = await api.scenarios.runs(s.id);
              run = runHistory.data[0] ?? null;
            } catch {
              run = null;
            }

            const series = run?.trajectory.map((p) => parseFloat(p.net) / 1_000_000) ?? [];
            const years = run?.trajectory.map((p) => String(currentYear + p.year)) ?? [];
            const withdrawalRate = parseFloat(s.withdrawal_rate);
            const incomeSeries =
              run?.retirement_trajectory?.map(
                (p) => (parseFloat(p.balance) * withdrawalRate) / 12,
              ) ?? [];

            return {
              id: s.id,
              name: s.name,
              description: s.description ?? "",
              netWorthAt65: run ? parseFloat(run.net_worth_at_target_age) : 0,
              monthlyIncomeAtLifeExpectancy: run?.monthly_sustainable_withdrawal
                ? parseFloat(run.monthly_sustainable_withdrawal)
                : 0,
              retirementAge: s.retirement_age,
              monthlyContribution: parseFloat(s.monthly_contribution),
              expectedReturn: parseFloat(s.expected_return),
              desiredMonthlyIncomeToday: s.desired_monthly_income_today
                ? parseFloat(s.desired_monthly_income_today)
                : null,
              withdrawalRate,
              successRate: run?.success_rate ? Math.round(parseFloat(run.success_rate) * 1000) / 10 : 0,
              color: CHART_COLORS[i % CHART_COLORS.length],
              series,
              incomeSeries,
              years,
            };
          }),
        );

        // --- insights + financial health -----------------------------------
        const insights: Insight[] = insightRows.map((ins) => ({
          id: ins.id,
          kind: ins.kind,
          text: ins.text,
          meta: ins.meta,
          generatedAt: ins.generated_at,
        }));

        const financialHealth: FinancialHealth | null = health
          ? {
              overall: health.overall,
              liquidity: health.liquidity,
              diversification: health.diversification,
              debtRatio: health.debt_ratio,
              savingsDiscipline: health.savings_discipline,
            }
          : null;

        const profile: ProfileSummary = {
          currentAge,
          currentRetirementBalance: retirementBalance,
          netWorthToday,
          targetRetirementAge: planningProfile.target_retirement_age,
          expectedReturn: planningProfile.expected_return,
          monthlySurplusEstimate: Math.max(0, Math.round(averageMonthlySurplus)),
        };

        const userAccount: UserAccountDetails = {
          fullName: user.full_name,
          email: user.email,
          baseCurrency: user.base_currency,
          dateOfBirth: user.date_of_birth,
          targetRetirementAge: planningProfile.target_retirement_age,
          targetEquityAllocation: parseFloat(planningProfile.target_equity_allocation),
          defaultWithdrawalRate: parseFloat(planningProfile.default_withdrawal_rate),
          includeSocialSecurity: planningProfile.include_social_security,
        };

        if (!cancelled) {
          setError(warnings.length ? `Some dashboard data could not be loaded: ${warnings.join(", ")}.` : null);
          setState({
            kpis,
            netWorthSeries,
            allocation,
            allocationMeta,
            cashflowSeries,
            accounts,
            institutions,
            transactions,
            milestones,
            recommendations,
            scenarios,
            insights,
            financialHealth,
            profile,
            userAccount,
          });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load your essential account data.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadAll();
    return () => {
      cancelled = true;
    };
  }, [status, refreshTick]);

  const value = useMemo<DataState>(
    () => ({ ...state, loading, error, refresh }),
    [state, loading, error, refresh],
  );

  if (status === "authenticated" && loading && state === emptyState) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <p className="text-[13px] text-muted-foreground">Loading your plan…</p>
      </div>
    );
  }

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

function useData(): DataState {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error("Data hooks must be used within a DataProvider");
  return ctx;
}

export const useKpis = () => useData().kpis;
export const useNetWorthSeries = () => useData().netWorthSeries;
export const useAllocation = () => useData().allocation;
export const useAllocationMeta = () => useData().allocationMeta;
export const useCashflowSeries = () => useData().cashflowSeries;
export const useAccountsData = () => useData().accounts;
export const useInstitutionsData = () => useData().institutions;
export const useTransactionsData = () => useData().transactions;
export const useMilestones = () => useData().milestones;
export const useRecommendationsData = () => useData().recommendations;
export const useScenariosData = () => useData().scenarios;
export const useCurrentAge = () => useData().profile?.currentAge ?? null;
export const useCurrentRetirementBalance = () => useData().profile?.currentRetirementBalance ?? null;
export const useInsightsData = () => useData().insights;
export const useFinancialHealthData = () => useData().financialHealth;
export const useProfileSummary = () => useData().profile;
export const useUserAccount = () => useData().userAccount;
export const useDataRefresh = () => useData().refresh;
export const useDataError = () => useData().error;
