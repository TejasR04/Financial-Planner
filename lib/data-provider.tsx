"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, type ApiAccount, type ApiScenarioPreview, type ApiTransaction } from "@/lib/api-client";
import {
  formatCurrency,
  type Account,
  type AllocationSlice,
  type CashflowPoint,
  type FinancialHealth,
  type Insight,
  type Institution,
  type Kpi,
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
  inflationRate: string;
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
  targetSavingsRate: number | null;
  cashReserveTarget: number | null;
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

type DashboardData = Pick<DataState, "kpis" | "netWorthSeries" | "allocation" | "allocationMeta" | "cashflowSeries">;
type AccountsData = Pick<DataState, "accounts" | "institutions">;
type InsightsData = Pick<DataState, "recommendations" | "insights" | "financialHealth">;
type ProfileData = Pick<DataState, "profile" | "userAccount">;
type DataMeta = Pick<DataState, "error" | "refresh">;

const DashboardContext = createContext<DashboardData | null>(null);
const AccountsContext = createContext<AccountsData | null>(null);
const TransactionsContext = createContext<Transaction[] | null>(null);
const ScenariosContext = createContext<Scenario[] | null>(null);
const InsightsContext = createContext<InsightsData | null>(null);
const ProfileContext = createContext<ProfileData | null>(null);
const DataMetaContext = createContext<DataMeta | null>(null);

const emptyState: Omit<DataState, "loading" | "error" | "refresh"> = {
  kpis: [],
  netWorthSeries: [],
  allocation: [],
  allocationMeta: null,
  cashflowSeries: [],
  accounts: [],
  institutions: [],
  transactions: [],
  recommendations: [],
  scenarios: [],
  insights: [],
  financialHealth: null,
  profile: null,
  userAccount: null,
};

export function DataProvider({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const pathname = usePathname();
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
          transactionRows,
          scenarioRows,
          recommendationRows,
          health,
          allocationAnalysis,
        ] = await Promise.all([
          api.users.me(),
          api.users.planningProfile(),
          api.accounts.list(),
          optional("institutions", api.accounts.institutions(), []),
          optional("recent transactions", api.transactions.listAll({ since: twelveMonthWindow().startDate }), []),
          optional("scenarios", api.scenarios.list(), []),
          optional("recommendations", api.recommendations.list("new"), []),
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
        const transactions: Transaction[] = transactionRows.map((t) => ({
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
        const cashflowSeries = buildCashflowSeries(transactionRows, window.start, window.end);
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

        // --- scenarios ----------------------------------------------------
        // Expensive projections are loaded separately, and only while the
        // projections route is active. This base load remains fast for every
        // other screen and never presents missing projections as zeroes.
        const retirementBalance = accountList.data
          .filter((a) => a.type === "retirement")
          .reduce((s, a) => s + parseFloat(a.balance), 0);

        const scenarios: Scenario[] = scenarioRows.map((s, i) => ({
          id: s.id,
          name: s.name,
          description: s.description ?? "",
          netWorthAt65: null,
          monthlyIncomeAtLifeExpectancy: null,
          retirementAge: s.retirement_age,
          monthlyContribution: parseFloat(s.monthly_contribution),
          expectedReturn: parseFloat(s.expected_return),
          inflationRate: parseFloat(s.inflation_rate),
          desiredMonthlyIncomeToday: s.desired_monthly_income_today
            ? parseFloat(s.desired_monthly_income_today)
            : null,
          withdrawalRate: parseFloat(s.withdrawal_rate),
          retirementYear: String(currentYear + s.retirement_age - currentAge),
          successRate: null,
          projectionStatus: "loading",
          color: CHART_COLORS[i % CHART_COLORS.length],
          series: [],
          withdrawals: [],
          years: [],
        }));

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
          inflationRate: planningProfile.inflation_rate,
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
          targetSavingsRate: planningProfile.target_savings_rate == null ? null : parseFloat(planningProfile.target_savings_rate),
          cashReserveTarget: planningProfile.cash_reserve_target == null ? null : parseFloat(planningProfile.cash_reserve_target),
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

  useEffect(() => {
    if (
      status !== "authenticated" ||
      pathname !== "/projections" ||
      !state.profile ||
      state.scenarios.length === 0 ||
      !state.scenarios.some((scenario) => scenario.projectionStatus === "loading")
    ) {
      return;
    }

    let cancelled = false;
    const scenarios = state.scenarios;
    const { currentAge, currentRetirementBalance } = state.profile;
    const currentYear = new Date().getFullYear();

    void Promise.all(
      scenarios.map(async (scenario) => {
        try {
          const preview = await api.scenarios.preview(scenario.id, {
            current_age: currentAge,
            current_retirement_balance: String(currentRetirementBalance),
            include_monte_carlo: true,
            monte_carlo_trials: 1000,
          });
          return { scenarioId: scenario.id, preview };
        } catch {
          return { scenarioId: scenario.id, preview: null };
        }
      }),
    ).then((results) => {
      if (cancelled) return;
      const previews = new Map(results.map((result) => [result.scenarioId, result.preview]));
      setState((current) => ({
        ...current,
        scenarios: current.scenarios.map((scenario) => {
          const preview: ApiScenarioPreview | null = previews.get(scenario.id) ?? null;
          if (!preview) {
            return {
              ...scenario,
              netWorthAt65: null,
              monthlyIncomeAtLifeExpectancy: null,
              successRate: null,
              projectionStatus: "unavailable",
              modelMetadata: undefined,
              series: [],
              withdrawals: [],
              years: [],
            };
          }
          return {
            ...scenario,
            netWorthAt65: parseFloat(preview.net_worth_at_target_age),
            monthlyIncomeAtLifeExpectancy: preview.monthly_sustainable_withdrawal
              ? parseFloat(preview.monthly_sustainable_withdrawal)
              : null,
            successRate: preview.success_rate
              ? Math.round(parseFloat(preview.success_rate) * 1000) / 10
              : null,
            projectionStatus: "available",
            modelMetadata: preview.model_metadata
              ? {
                  modelVersion: preview.model_metadata.model_version,
                  successMetric: preview.model_metadata.success_metric,
                  trials: preview.model_metadata.trials,
                  seed: preview.model_metadata.seed,
                  percentileMethod: preview.model_metadata.percentile_method,
                  exclusions: preview.model_metadata.exclusions,
                }
              : undefined,
            series: preview.retirement_trajectory.map((point) => parseFloat(point.balance) / 1_000_000),
            withdrawals: preview.retirement_trajectory.map((point) => parseFloat(point.withdrawal)),
            years: preview.retirement_trajectory.map((point) => String(currentYear + point.year)),
          };
        }),
      }));
    });

    return () => {
      cancelled = true;
    };
  }, [pathname, state.profile, state.scenarios, status]);

  const dashboardValue = useMemo<DashboardData>(() => ({
    kpis: state.kpis,
    netWorthSeries: state.netWorthSeries,
    allocation: state.allocation,
    allocationMeta: state.allocationMeta,
    cashflowSeries: state.cashflowSeries,
  }), [state.kpis, state.netWorthSeries, state.allocation, state.allocationMeta, state.cashflowSeries]);
  const accountsValue = useMemo<AccountsData>(() => ({
    accounts: state.accounts,
    institutions: state.institutions,
  }), [state.accounts, state.institutions]);
  const insightsValue = useMemo<InsightsData>(() => ({
    recommendations: state.recommendations,
    insights: state.insights,
    financialHealth: state.financialHealth,
  }), [state.recommendations, state.insights, state.financialHealth]);
  const profileValue = useMemo<ProfileData>(() => ({
    profile: state.profile,
    userAccount: state.userAccount,
  }), [state.profile, state.userAccount]);
  const metaValue = useMemo<DataMeta>(() => ({ error, refresh }), [error, refresh]);

  if (status === "authenticated" && loading && state === emptyState) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <p className="text-[13px] text-muted-foreground">Loading your plan…</p>
      </div>
    );
  }

  return (
    <DataMetaContext.Provider value={metaValue}>
      <ProfileContext.Provider value={profileValue}>
        <AccountsContext.Provider value={accountsValue}>
          <TransactionsContext.Provider value={state.transactions}>
            <DashboardContext.Provider value={dashboardValue}>
              <InsightsContext.Provider value={insightsValue}>
                <ScenariosContext.Provider value={state.scenarios}>
                  {children}
                </ScenariosContext.Provider>
              </InsightsContext.Provider>
            </DashboardContext.Provider>
          </TransactionsContext.Provider>
        </AccountsContext.Provider>
      </ProfileContext.Provider>
    </DataMetaContext.Provider>
  );
}

function useRequiredContext<T>(context: React.Context<T | null>): T {
  const ctx = useContext(context);
  if (!ctx) throw new Error("Data hooks must be used within a DataProvider");
  return ctx;
}

export const useKpis = () => useRequiredContext(DashboardContext).kpis;
export const useNetWorthSeries = () => useRequiredContext(DashboardContext).netWorthSeries;
export const useAllocation = () => useRequiredContext(DashboardContext).allocation;
export const useAllocationMeta = () => useRequiredContext(DashboardContext).allocationMeta;
export const useCashflowSeries = () => useRequiredContext(DashboardContext).cashflowSeries;
export const useAccountsData = () => useRequiredContext(AccountsContext).accounts;
export const useInstitutionsData = () => useRequiredContext(AccountsContext).institutions;
export const useTransactionsData = () => useRequiredContext(TransactionsContext);
export const useRecommendationsData = () => useRequiredContext(InsightsContext).recommendations;
export const useScenariosData = () => useRequiredContext(ScenariosContext);
export const useCurrentAge = () => useRequiredContext(ProfileContext).profile?.currentAge ?? null;
export const useCurrentRetirementBalance = () => useRequiredContext(ProfileContext).profile?.currentRetirementBalance ?? null;
export const useInsightsData = () => useRequiredContext(InsightsContext).insights;
export const useFinancialHealthData = () => useRequiredContext(InsightsContext).financialHealth;
export const useProfileSummary = () => useRequiredContext(ProfileContext).profile;
export const useUserAccount = () => useRequiredContext(ProfileContext).userAccount;
export const useDataRefresh = () => useRequiredContext(DataMetaContext).refresh;
export const useDataError = () => useRequiredContext(DataMetaContext).error;
