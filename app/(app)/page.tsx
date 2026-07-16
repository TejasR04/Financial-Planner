import { Download, Filter } from "lucide-react";
import { PageContainer, PageHeader } from "@/components/page-container";
import { Panel, PanelHeader } from "@/components/panel";
import { KpiCard } from "@/components/kpi-card";
import { NetWorthChart } from "@/components/charts/net-worth-chart";
import { AllocationChart } from "@/components/charts/allocation-chart";
import { CashflowChart } from "@/components/charts/cashflow-chart";
import { TransactionsTable } from "@/components/transactions-table";
import { Timeline } from "@/components/timeline";
import { AiInsights } from "@/components/ai-insights";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { kpis } from "@/lib/data";

export default function OverviewPage() {
  return (
    <PageContainer>
      <PageHeader
        title="Overview"
        description="Consolidated position across 8 linked accounts · updated 4 minutes ago"
        actions={
          <>
            <Button variant="outline" size="sm">
              <Filter />
              Last 12 months
            </Button>
            <Button variant="outline" size="sm">
              <Download />
              Export
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
              </div>
            }
          />
          <NetWorthChart />
        </Panel>

        <Panel>
          <PanelHeader
            title="Asset allocation"
            description="Target 42% equities"
            actions={<Badge variant="warning">4% drift</Badge>}
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
              <Button variant="ghost" size="xs">
                View all
              </Button>
            }
          />
          <TransactionsTable />
        </Panel>

        <AiInsights className="xl:col-span-1" />
      </div>

      {/* Cashflow + timeline */}
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2">
          <PanelHeader
            title="Cash flow"
            description="Monthly income vs. tracked expenses"
            actions={
              <div className="flex items-center gap-3 text-[11px]">
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
          <CashflowChart />
        </Panel>

        <Panel>
          <PanelHeader
            title="Life plan"
            description="Milestones on your trajectory"
          />
          <Timeline />
        </Panel>
      </div>
    </PageContainer>
  );
}
