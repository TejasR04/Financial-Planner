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
import { api, type ApiAccount, type ApiScenarioRun } from "@/lib/api-client";
import {
  formatCurrency,
  type Account,
  type AllocationSlice,
  type CashflowPoint,
  type FinancialHealth,
  type Insight,
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
        const [
          user,
          planningProfile,
          accountList,
          transactionList,
          goals,
          scenarioRows,
          recommendationRows,
          insightRows,
          health,
          allocationAnalysis,
        ] = await Promise.all([
          api.users.me(),
          api.users.planningProfile(),
          api.accounts.list(),
          api.transactions.list({ limit: 200 }),
          api.goals.list(),
          api.scenarios.list(),
          api.recommendations.list(),
          api.insights.list(),
          api.financialHealth.get(),
          api.accounts.allocation(),
        ]);

        const currentAge = ageFromBirthDate(user.date_of_birth);
        const currentYear = new Date().getFullYear();

        // --- accounts -------------------------------------------------
        const accounts: Account[] = accountList.data.map((a) => ({
          id: a.id,
          name: a.name,
          institution: a.institution ?? undefined,
          type: ACCOUNT_TYPE_LABEL[a.type],
          mask: a.mask ?? "—",
          balance: parseFloat(a.balance),
          apy: a.apy != null ? parseFloat(a.apy) : undefined,
          status: a.status,
          updated: formatRelativeTime(a.updated_at),
        }));
        const accountNameById = new Map(
          accountList.data.map((a) => [a.id, a.name]),
        );

        // --- kpis (net worth + liquid assets are real; no fabricated
        // deltas/sparklines — see lib/data.ts) -------------------------
        const netWorthToday = parseFloat(accountList.net_worth);
        const liquidAssets = accountList.data
          .filter((a) => a.type === "depository")
          .reduce((s, a) => s + parseFloat(a.balance), 0);
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
            hint: "Cash and cash-equivalent holdings",
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
            years: 10,
            expected_return: planningProfile.expected_return,
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
        const allocation: AllocationSlice[] = allocationAnalysis.breakdown.map(
          (b, i) => ({
            name: ASSET_CLASS_LABEL[b.asset_class] ?? b.asset_class,
            value: Math.round(parseFloat(b.weight) * 1000) / 10,
            amount: parseFloat(b.market_value),
            color: CHART_COLORS[i % CHART_COLORS.length],
          }),
        );
        const allocationMeta: AllocationMeta = {
          targetEquityPercent:
            Math.round(
              parseFloat(allocationAnalysis.target_equity_allocation) * 1000,
            ) / 10,
          driftPercent:
            Math.round(parseFloat(allocationAnalysis.drift) * 1000) / 10,
          isWithinTolerance: allocationAnalysis.is_within_tolerance,
        };

        // --- transactions + cashflow (real, aggregated from posted_at) --
        const transactions: Transaction[] = transactionList.data.map((t) => ({
          id: t.id,
          date: formatShortDate(t.posted_at),
          merchant: t.merchant,
          category: t.category,
          account: accountNameById.get(t.account_id) ?? "Account",
          amount: parseFloat(t.amount),
          status: t.status,
        }));

        const cashflowByMonth = new Map<
          string,
          { income: number; expenses: number }
        >();
        for (const t of transactionList.data) {
          const d = new Date(`${t.posted_at}T00:00:00`);
          const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
          const bucket = cashflowByMonth.get(key) ?? { income: 0, expenses: 0 };
          const amount = parseFloat(t.amount);
          if (amount >= 0) bucket.income += amount;
          else bucket.expenses += -amount;
          cashflowByMonth.set(key, bucket);
        }
        const cashflowSeries: CashflowPoint[] = Array.from(
          cashflowByMonth.entries(),
        )
          .sort(([a], [b]) => a.localeCompare(b))
          .slice(-6)
          .map(([key, v]) => {
            const [y, m] = key.split("-");
            const label = new Date(
              Number(y),
              Number(m) - 1,
              1,
            ).toLocaleDateString("en-US", {
              month: "short",
            });
            return { month: label, income: v.income, expenses: v.expenses };
          });

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
            amount: formatCurrency(parseFloat(g.target_amount), {
              compact: true,
            }),
            status: g.status,
          };
        });

        // --- recommendations ----------------------------------------------
        let recRows = recommendationRows;
        if (recRows.length === 0) {
          try {
            recRows = await api.recommendations.generate();
          } catch {
            // leave empty if generation fails — page still renders
          }
        }
        const recommendations: Recommendation[] = recRows.map((r) => ({
          id: r.id,
          title: r.title,
          body: r.body,
          impact: `${formatCurrency(parseFloat(r.impact_value), { sign: true })} / yr`,
          impactValue: parseFloat(r.impact_value),
          effort: (r.effort.charAt(0).toUpperCase() +
            r.effort.slice(1)) as Recommendation["effort"],
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
              if (!run) {
                run = await api.scenarios.run(s.id, {
                  current_age: currentAge,
                  current_retirement_balance: String(retirementBalance),
                  include_monte_carlo: true,
                  monte_carlo_trials: 1000,
                });
              }
            } catch {
              run = null;
            }

            const series =
              run?.trajectory.map((p) => parseFloat(p.net) / 1_000_000) ?? [];
            const years =
              run?.trajectory.map((p) => String(currentYear + p.year)) ?? [];

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
              successRate: run?.success_rate
                ? Math.round(parseFloat(run.success_rate) * 1000) / 10
                : 0,
              color: CHART_COLORS[i % CHART_COLORS.length],
              series,
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
        }));

        const financialHealth: FinancialHealth = {
          overall: health.overall,
          liquidity: health.liquidity,
          diversification: health.diversification,
          debtRatio: health.debt_ratio,
          savingsDiscipline: health.savings_discipline,
        };

        const avgMonthlySurplus =
          cashflowSeries.length > 0
            ? cashflowSeries.reduce((s, c) => s + (c.income - c.expenses), 0) /
              cashflowSeries.length
            : 0;
        const profile: ProfileSummary = {
          currentAge,
          netWorthToday,
          targetRetirementAge: planningProfile.target_retirement_age,
          expectedReturn: planningProfile.expected_return,
          monthlySurplusEstimate: Math.max(0, Math.round(avgMonthlySurplus)),
        };

        const userAccount: UserAccountDetails = {
          fullName: user.full_name,
          email: user.email,
          baseCurrency: user.base_currency,
          dateOfBirth: user.date_of_birth,
          targetRetirementAge: planningProfile.target_retirement_age,
          targetEquityAllocation: parseFloat(
            planningProfile.target_equity_allocation,
          ),
          defaultWithdrawalRate: parseFloat(
            planningProfile.default_withdrawal_rate,
          ),
          includeSocialSecurity: planningProfile.include_social_security,
        };

        if (!cancelled) {
          setState({
            kpis,
            netWorthSeries,
            allocation,
            allocationMeta,
            cashflowSeries,
            accounts,
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
          setError(
            err instanceof Error ? err.message : "Failed to load your data.",
          );
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
export const useTransactionsData = () => useData().transactions;
export const useMilestones = () => useData().milestones;
export const useRecommendationsData = () => useData().recommendations;
export const useScenariosData = () => useData().scenarios;
export const useCurrentAge = () => useData().profile?.currentAge ?? null;
export const useInsightsData = () => useData().insights;
export const useFinancialHealthData = () => useData().financialHealth;
export const useProfileSummary = () => useData().profile;
export const useUserAccount = () => useData().userAccount;
export const useDataRefresh = () => useData().refresh;
