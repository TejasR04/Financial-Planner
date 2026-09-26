"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, clearApiCache, type ApiAccount, type ApiScenarioPreview, type ApiTransaction } from "@/lib/api-client";
import {
  ageFromBirthDate,
  buildCashflowSeries,
  formatShortDate,
  formatTimestamp,
  twelveMonthWindow,
} from "@/lib/dashboard-data-helpers";
import { RESPONSE_CACHE_TTL_MS } from "@/lib/response-cache";
import { retirementPortfolioBalance } from "@/lib/retirement-portfolio";
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
  currentAge: number | null;
  currentRetirementBalance: number;
  netWorthToday: number;
  targetRetirementAge: number;
  expectedReturn: string; // decimal string, e.g. "0.065" — as the API expects
  inflationRate: string;
  defaultWithdrawalRate: number;
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
type DataMeta = Pick<DataState, "error" | "refresh"> & { generation: number };

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
  const { status: authStatus, isDemo } = useAuth();
  const status = isDemo ? "authenticated" : authStatus;
  const pathname = usePathname();
  const [state, setState] = useState(emptyState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const modeRef = useRef(isDemo);

  useLayoutEffect(() => {
    if (modeRef.current === isDemo) return;
    modeRef.current = isDemo;
    setState(emptyState);
    setLoading(true);
    setError(null);
  }, [isDemo]);

  const lastRefreshAt = useRef(Date.now());
  const refresh = useCallback(() => {
    clearApiCache();
    lastRefreshAt.current = Date.now();
    setRefreshTick((t) => t + 1);
  }, []);

  useEffect(() => {
    const refreshIfStale = () => {
      if (status === "authenticated" && Date.now() - lastRefreshAt.current >= RESPONSE_CACHE_TTL_MS) refresh();
    };
    refreshIfStale();
    window.addEventListener("focus", refreshIfStale);
    return () => window.removeEventListener("focus", refreshIfStale);
  }, [pathname, refresh, status]);

  useEffect(() => {
    if (status !== "authenticated") return;
    let cancelled = false;
    const controller = new AbortController();

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
          investmentDashboard,
          activitySummary,
          budgetCategories,
        ] = await Promise.all([
          api.users.me(),
          api.users.planningProfile(),
          api.accounts.list(),
          optional("institutions", api.accounts.institutions(), []),
          optional(
            "recent transactions",
            api.transactions.listAll(
              { since: twelveMonthWindow().startDate },
              controller.signal,
            ),
            [],
          ),
          optional("scenarios", api.scenarios.list(), []),
          optional("recommendations", api.recommendations.list("new"), []),
          optional("financial health", api.financialHealth.get(), null, false),
          optional("allocation", api.accounts.allocation(), null),
          optional("investment details", api.investments.dashboard(), null, false),
          optional("activity summary", api.activity.summary(), null, false),
          optional("budget categories", api.budgets.categories(controller.signal), []),
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
          reportedCashBalance: a.reported_cash_balance == null ? null : parseFloat(a.reported_cash_balance),
          reportedCashIsLiquid: a.reported_cash_is_liquid,
          apy: a.apy != null ? parseFloat(a.apy) : undefined,
          status: a.institution_status === "error" || a.institution_status === "action_required" ? "attention" : a.status,
          updated: formatTimestamp(a.institution_last_synced_at ?? a.updated_at),
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
          category: t.budget_category_name ?? (t.type === "credit_card_payment" ? "Credit card payment" : t.type === "income" ? "Income" : t.type === "transfer" ? "Transfer" : "Uncategorized"),
          account: t.account_name ?? accountNameById.get(t.account_id) ?? "Account",
          amount: parseFloat(t.amount),
          type: t.type,
          status: t.status,
        }));
        const activeCategoryIds = new Set(budgetCategories.filter((category) => category.active).map((category) => category.id));
        const cashflowSeries = buildCashflowSeries(
          transactionRows,
          window.start,
          window.end,
          new Date(),
          activitySummary?.history_start,
          activeCategoryIds,
        );
        // Do not treat months before the first imported transaction as real
        // zero-income months. Plaid history can be shorter than the chart's
        // requested 12-month window.
        // The current month is incomplete and would depress both KPIs early
        // in the month. Keep it on the chart, but calculate the headline
        // cash-flow and savings-rate figures from completed months only.
        const averageMonthlyIncome = activitySummary?.average_monthly_income == null ? null : parseFloat(activitySummary.average_monthly_income);
        const averageMonthlyExpenses = activitySummary?.average_monthly_expenses == null ? null : parseFloat(activitySummary.average_monthly_expenses);
        const averageMonthlySurplus = activitySummary?.average_monthly_surplus == null ? null : parseFloat(activitySummary.average_monthly_surplus);

        // --- kpis (all values are based on the selected trailing window)
        const netWorthToday = parseFloat(accountList.net_worth);
        const taxableInvestmentIds = new Set(
          accountList.data
            .filter((account) => account.type === "investment" && account.reported_cash_balance == null)
            .map((account) => account.id),
        );
        const cashHoldings = (investmentDashboard?.holdings ?? [])
          .filter((holding) => holding.asset_class === "cash" && taxableInvestmentIds.has(holding.account_id))
          .reduce((sum, holding) => sum + parseFloat(holding.market_value), 0);
        const reportedLiquidCash = accountList.data
          .filter((account) => (account.type === "investment" || account.type === "retirement") && account.reported_cash_is_liquid && account.reported_cash_balance != null)
          .reduce((sum, account) => sum + Math.max(0, Number(account.reported_cash_balance)), 0);
        const liquidAssets = accountList.data
          .filter((a) => a.type === "depository" && parseFloat(a.balance) > 0)
          .reduce((s, a) => s + parseFloat(a.balance), 0) + cashHoldings + reportedLiquidCash;
        const savingsRate = averageMonthlyIncome != null && averageMonthlyIncome > 0 && averageMonthlySurplus != null ? (averageMonthlySurplus / averageMonthlyIncome) * 100 : null;
        const rangeLabel = activitySummary?.label ?? "No completed months available";
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
            hint: "Positive depository balances plus cash holdings in taxable brokerage accounts",
          },
          {
            id: "monthly-cash-flow",
            label: "Average monthly cash flow",
            value: averageMonthlySurplus == null ? "—" : formatCurrency(averageMonthlySurplus, { sign: true }),
            raw: averageMonthlySurplus ?? 0,
            hint: `Income less expenses · ${rangeLabel}`,
          },
          {
            id: "savings-rate",
            label: "Savings Rate",
            value: savingsRate == null ? "—" : `${savingsRate.toFixed(1)}%`,
            raw: savingsRate ?? 0,
            hint: `Income retained after expenses · ${rangeLabel}`,
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
        if (currentAge != null) try {
          const projection = await api.simulations.netWorth({
            current_age: currentAge,
            retirement_age: planningProfile.target_retirement_age,
            years: Math.max(1, planningProfile.target_retirement_age - currentAge),
            expected_return: planningProfile.expected_return,
            annual_net_contribution: String(Math.max(0, averageMonthlySurplus ?? 0) * 12),
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
        const retirementBalance = retirementPortfolioBalance(accountList.data);

        const scenarios: Scenario[] = scenarioRows.map((s, i) => ({
          id: s.id,
          name: s.name,
          description: s.description ?? "",
          netWorthAt65: null,
          monthlyIncomeAtLifeExpectancy: null,
          withdrawalRateCapacity: null,
          retirementAge: s.retirement_age,
          monthlyContribution: parseFloat(s.monthly_contribution),
          expectedReturn: parseFloat(s.expected_return),
          inflationRate: parseFloat(s.inflation_rate),
          desiredMonthlyIncomeToday: s.desired_monthly_income_today
            ? parseFloat(s.desired_monthly_income_today)
            : null,
          withdrawalRate: parseFloat(s.withdrawal_rate),
          retirementYear: currentAge == null ? "Age needed" : String(currentYear + s.retirement_age - currentAge),
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
          defaultWithdrawalRate: parseFloat(planningProfile.default_withdrawal_rate),
          monthlySurplusEstimate: Math.max(0, Math.round(averageMonthlySurplus ?? 0)),
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
      controller.abort();
    };
  }, [status, isDemo, refreshTick]);

  useEffect(() => {
    if (
      status !== "authenticated" ||
      pathname !== "/projections" ||
      !state.profile ||
      state.profile.currentAge == null ||
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
              withdrawalRateCapacity: null,
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
            // The summary card shows the invested portfolio available for
            // retirement; the chart below separately shows total net worth.
            netWorthAt65: parseFloat(
              preview.retirement_balance_at_target_age
                ?? preview.retirement_trajectory.find((point) => point.age === scenario.retirementAge)?.balance
                ?? preview.net_worth_at_target_age,
            ),
            monthlyIncomeAtLifeExpectancy: scenario.desiredMonthlyIncomeToday
              ?? (preview.monthly_sustainable_withdrawal ? parseFloat(preview.monthly_sustainable_withdrawal) : null),
            withdrawalRateCapacity: preview.monthly_sustainable_withdrawal
              ? parseFloat(preview.monthly_sustainable_withdrawal)
              : null,
            successRate: preview.success_rate != null
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
            // The scenario chart is a total net-worth projection, so use its
            // matching net-worth trajectory (including current year zero).
            series: preview.trajectory.map((point) => parseFloat(String(point.net)) / 1_000_000),
            withdrawals: preview.retirement_trajectory.map((point) => parseFloat(point.withdrawal)),
            years: preview.trajectory.map((point) => String(currentYear + Number(point.year))),
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
  const metaValue = useMemo<DataMeta>(() => ({ error, refresh, generation: refreshTick }), [error, refresh, refreshTick]);

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
export const useDataGeneration = () => useRequiredContext(DataMetaContext).generation;
export const useDataError = () => useRequiredContext(DataMetaContext).error;
