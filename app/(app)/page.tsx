"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageContainer, PageHeader } from "@/components/page-container";
import { Panel, PanelHeader } from "@/components/panel";
import { KpiCard } from "@/components/kpi-card";
import { NetWorthChart } from "@/components/charts/net-worth-chart";
import { NetWorthHistoryChart } from "@/components/charts/net-worth-history-chart";
import { AllocationChart } from "@/components/charts/allocation-chart";
import { CashFlowPanel } from "@/components/cash-flow-panel";
import { TransactionsTable } from "@/components/transactions-table";
import { RuleBasedInsights } from "@/components/rule-based-insights";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAccountsData, useAllocationMeta, useKpis } from "@/lib/data-provider";

export default function OverviewPage() {
  const router = useRouter();
  const [netWorthTab, setNetWorthTab] = useState<"history" | "projection">("history");
  const kpis = useKpis();
  const accounts = useAccountsData();
  const allocationMeta = useAllocationMeta();
  return <PageContainer>
    <PageHeader title="Overview" description={`Consolidated position across ${accounts.length} account${accounts.length === 1 ? "" : "s"}`} />
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">{kpis.map((kpi) => <KpiCard key={kpi.id} kpi={kpi} />)}</div>
    <div className="mt-4"><CashFlowPanel /></div>
    <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
      <Panel className="xl:col-span-2">
        <PanelHeader title="Recent activity" description="Latest transactions across all accounts" actions={<Button variant="ghost" size="xs" onClick={() => router.push("/transactions")}>View all</Button>} />
        <TransactionsTable />
      </Panel>
      <RuleBasedInsights />
    </div>
    <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
      <Panel className="xl:col-span-2">
        <PanelHeader title={netWorthTab === "history" ? "Net worth history" : "Projected net worth"}
          description={netWorthTab === "history" ? "Recorded account totals over time" : "Today's position followed by a projection to retirement"}
          actions={netWorthTab === "projection" ? <Button variant="ghost" size="xs" onClick={() => router.push("/projections")}>Explore assumptions</Button> : undefined} />
        <div role="tablist" aria-label="Net worth chart view" className="flex gap-1 px-4 pt-3">
          {(["history", "projection"] as const).map((tab) => <button key={tab} id={`net-worth-tab-${tab}`} type="button" role="tab"
            aria-selected={netWorthTab === tab} aria-controls="net-worth-chart-panel" onClick={() => setNetWorthTab(tab)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${netWorthTab === tab ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>{tab === "history" ? "History" : "Projection"}</button>)}
        </div>
        <div className="flex gap-4 px-4 pt-3 text-xs text-muted-foreground"><span>Net worth</span><span>Assets (dashed blue)</span><span>Liabilities (dashed orange)</span></div>
        <div id="net-worth-chart-panel" role="tabpanel" aria-labelledby={`net-worth-tab-${netWorthTab}`}>
          {netWorthTab === "history" ? <NetWorthHistoryChart /> : <NetWorthChart />}
        </div>
        {netWorthTab === "history" && <p className="border-t border-border px-4 py-2.5 text-[11px] text-muted-foreground">History starts with the first recorded daily snapshot. Earlier account balances cannot be reconstructed from current values.</p>}
      </Panel>
      <Panel>
        <PanelHeader title="Investment allocation" description={allocationMeta ? `Investment holdings · target ${allocationMeta.targetEquityPercent}% equities` : "Investment holdings"} actions={allocationMeta && Math.abs(allocationMeta.driftPercent) > 0 ? <Badge variant={allocationMeta.isWithinTolerance ? "outline" : "warning"}>{Math.abs(allocationMeta.driftPercent)} pp from target</Badge> : undefined} />
        <AllocationChart />
      </Panel>
    </div>
  </PageContainer>;
}
