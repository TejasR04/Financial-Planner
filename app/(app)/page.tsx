"use client";

import { useRouter } from "next/navigation";
import { PageContainer, PageHeader } from "@/components/page-container";
import { Panel, PanelHeader } from "@/components/panel";
import { KpiCard } from "@/components/kpi-card";
import { NetWorthChart } from "@/components/charts/net-worth-chart";
import { AllocationChart } from "@/components/charts/allocation-chart";
import { CashFlowPanel } from "@/components/cash-flow-panel";
import { TransactionsTable } from "@/components/transactions-table";
import { RuleBasedInsights } from "@/components/rule-based-insights";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAccountsData, useAllocationMeta, useKpis } from "@/lib/data-provider";

export default function OverviewPage() {
  const router = useRouter();
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
        <PanelHeader title="Projected net worth" description="Today's position followed by a projection to retirement" actions={<Button variant="ghost" size="xs" onClick={() => router.push("/projections")}>Explore assumptions</Button>} />
        <div className="flex gap-4 px-4 pt-3 text-xs text-muted-foreground"><span>Net worth</span><span>Assets (dashed blue)</span><span>Liabilities (dashed orange)</span></div>
        <NetWorthChart />
      </Panel>
      <Panel>
        <PanelHeader title="Investment allocation" description={allocationMeta ? `Investment holdings · target ${allocationMeta.targetEquityPercent}% equities` : "Investment holdings"} actions={allocationMeta && Math.abs(allocationMeta.driftPercent) > 0 ? <Badge variant={allocationMeta.isWithinTolerance ? "outline" : "warning"}>{Math.abs(allocationMeta.driftPercent)} pp from target</Badge> : undefined} />
        <AllocationChart />
      </Panel>
    </div>
  </PageContainer>;
}
