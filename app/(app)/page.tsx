"use client";

import { Download } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { PageContainer, PageHeader } from "@/components/page-container";
import { Panel, PanelHeader } from "@/components/panel";
import { KpiCard } from "@/components/kpi-card";
import { NetWorthChart } from "@/components/charts/net-worth-chart";
import { AllocationChart } from "@/components/charts/allocation-chart";
import { CashflowChart } from "@/components/charts/cashflow-chart";
import { TransactionsTable } from "@/components/transactions-table";
import { RuleBasedInsights } from "@/components/rule-based-insights";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAccountsData, useAllocationMeta, useCashflowSeries, useKpis, useTransactionsData } from "@/lib/data-provider";
import { exportTransactionsCsv } from "@/lib/transaction-export";
import { api } from "@/lib/api-client";
import type { CashflowPoint } from "@/lib/data";

export default function OverviewPage() {
  const router = useRouter();
  const kpis = useKpis();
  const accounts = useAccountsData();
  const allocationMeta = useAllocationMeta();
  const cashflowSeries = useCashflowSeries();
  const transactions = useTransactionsData();
  const [periodMonths, setPeriodMonths] = useState<6 | 12>(12);
  const [cashflowMode, setCashflowMode] = useState<"actuals" | "outlook">("actuals");
  const [outlook, setOutlook] = useState<CashflowPoint[] | null>(null);
  const [outlookNote, setOutlookNote] = useState<string | null>(null);
  const visibleCashflow = useMemo(() => cashflowSeries.slice(-periodMonths), [cashflowSeries, periodMonths]);
  useEffect(() => {
    if (cashflowMode !== "outlook") return;
    let cancelled = false;
    api.simulations.cashFlow(periodMonths).then((result) => {
      if (cancelled) return;
      const formatter = new Intl.DateTimeFormat("en-US", { month: "short" });
      setOutlook(result.series.map((point) => { const d = new Date(); d.setMonth(d.getMonth() + point.month_index - 1); return { month: formatter.format(d), income: Number(point.income), expenses: Number(point.expenses) }; }));
      setOutlookNote(`${result.income_source} · ${result.expense_source}`);
    }).catch((error) => {
      if (!cancelled) {
        setOutlook([]);
        setOutlookNote(error instanceof Error ? error.message : "Outlook unavailable.");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [cashflowMode, periodMonths]);

  const exportTransactions = () => {
    const cutoff = new Date();
    cutoff.setMonth(cutoff.getMonth() - (periodMonths - 1), 1);
    const exportRows = transactions
      .filter((transaction) => new Date(`${transaction.postedAt}T00:00:00`) >= cutoff)
    exportTransactionsCsv(exportRows, `meridian-transactions-last-${periodMonths}-months.csv`);
  };

  return (
    <PageContainer>
      <PageHeader
        title="Overview"
        description={`Consolidated position across ${accounts.length} linked account${accounts.length === 1 ? "" : "s"}`}
        actions={
          <>
            <label className="flex h-7 items-center gap-1 rounded-md border border-border bg-background px-2 text-[0.8rem] text-foreground">
              <span className="sr-only">Cash-flow period</span>
              <select
                value={periodMonths}
                onChange={(event) => setPeriodMonths(Number(event.target.value) as 6 | 12)}
                className="bg-transparent outline-none"
              >
                <option value={6}>Last 6 months</option>
                <option value={12}>Last 12 months</option>
              </select>
            </label>
            <Button variant="outline" size="sm" onClick={exportTransactions}>
              <Download />
              Export CSV
            </Button>
          </>
        }
      />

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.id} kpi={kpi} />
        ))}
      </div>

      {/* Net worth + allocation */}
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2">
          <PanelHeader
            title="Net worth"
            description="Assets, liabilities, and net position over time"
            actions={
              <div className="flex items-center gap-3 text-[11px]">
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <span className="size-2 rounded-[2px] bg-chart-1" />
                  Net worth
                </span>
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <span className="size-2 rounded-[2px] bg-chart-2" />
                  Assets
                </span>
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <span className="size-2 rounded-[2px] bg-chart-4" />
                  Liabilities
                </span>
              </div>
            }
          />
          <NetWorthChart />
        </Panel>

        <Panel>
          <PanelHeader
            title="Asset allocation"
            description={
              allocationMeta ? `Target ${allocationMeta.targetEquityPercent}% equities` : "Target allocation"
            }
            actions={
              allocationMeta && Math.abs(allocationMeta.driftPercent) > 0 ? (
                <Badge variant={allocationMeta.isWithinTolerance ? "outline" : "warning"}>
                  {Math.abs(allocationMeta.driftPercent)}% drift
                </Badge>
              ) : undefined
            }
          />
          <AllocationChart />
        </Panel>
      </div>

      {/* Transactions + AI insights */}
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2">
          <PanelHeader
            title="Recent activity"
            description="Latest transactions across all accounts"
            actions={
              <Button variant="ghost" size="xs" onClick={() => router.push("/transactions")}>
                View all
              </Button>
            }
          />
          <TransactionsTable />
        </Panel>

        <RuleBasedInsights className="xl:col-span-1" />
      </div>

      <div className="mt-4">
        <Panel>
          <PanelHeader
            title="Cash flow"
            description={cashflowMode === "actuals" ? `Historical transaction actuals · last ${periodMonths} months` : outlookNote ?? "Loading planning outlook…"}
            actions={
              <div className="flex items-center gap-2 text-[11px]">
                <Button variant={cashflowMode === "actuals" ? "outline" : "ghost"} size="xs" onClick={() => setCashflowMode("actuals")}>Actuals</Button>
                <Button variant={cashflowMode === "outlook" ? "outline" : "ghost"} size="xs" onClick={() => setCashflowMode("outlook")}>Outlook</Button>
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <span className="size-2 rounded-[2px] bg-chart-1" />
                  Income
                </span>
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <span className="size-2 rounded-[2px] bg-chart-4" />
                  Expenses
                </span>
              </div>
            }
          />
          <CashflowChart data={cashflowMode === "actuals" ? visibleCashflow : outlook ?? []} />
        </Panel>

      </div>
    </PageContainer>
  );
}

