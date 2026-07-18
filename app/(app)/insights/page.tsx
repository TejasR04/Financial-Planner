"use client";

import { useState } from "react";
import { Sparkles, RefreshCw } from "lucide-react";
import { PageContainer, PageHeader } from "@/components/page-container";
import { Panel, PanelHeader } from "@/components/panel";
import { RecommendationCard } from "@/components/recommendation-card";
import { AiInsights } from "@/components/ai-insights";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/data";
import { useDataRefresh, useFinancialHealthData, useRecommendationsData } from "@/lib/data-provider";
import { api } from "@/lib/api-client";

function healthLabel(score: number) {
  if (score >= 80) return "Strong";
  if (score >= 60) return "Good";
  if (score >= 40) return "Fair";
  return "Needs attention";
}

export default function InsightsPage() {
  const recommendations = useRecommendationsData();
  const financialHealth = useFinancialHealthData();
  const refresh = useDataRefresh();
  const [rerunning, setRerunning] = useState(false);

  const totalImpact = recommendations.reduce((s, r) => s + r.impactValue, 0);

  async function handleRerun() {
    setRerunning(true);
    try {
      await Promise.all([api.recommendations.generate(), api.financialHealth.recalculate()]);
      refresh();
    } finally {
      setRerunning(false);
    }
  }

  const healthRows = financialHealth
    ? [
        { label: "Liquidity", score: financialHealth.liquidity },
        { label: "Diversification", score: financialHealth.diversification },
        { label: "Debt ratio", score: financialHealth.debtRatio },
        { label: "Savings discipline", score: financialHealth.savingsDiscipline },
      ]
    : [];

  return (
    <PageContainer>
      <PageHeader
        title="Insights"
        description="AI-surfaced recommendations ranked by projected impact and confidence"
        actions={
          <Button variant="outline" size="sm" onClick={handleRerun} disabled={rerunning}>
            <RefreshCw className={rerunning ? "animate-spin" : undefined} />
            Re-run analysis
          </Button>
        }
      />

      {/* Summary banner */}
      <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
            <Sparkles className="size-5 text-primary" />
          </span>
          <div>
            <p className="text-[14px] font-semibold tracking-tight text-foreground">
              {recommendations.length} opportunities identified this cycle
            </p>
            <p className="mt-0.5 text-[13px] text-muted-foreground text-pretty">
              Acting on all recommendations is modeled to improve annual
              outcomes by roughly{" "}
              <span className="font-medium text-positive">
                {formatCurrency(totalImpact)}
              </span>
              .
            </p>
          </div>
        </div>
        <Button size="sm" className="shrink-0">
          Apply all safe actions
        </Button>
      </div>

      {/* Recommendations + insights */}
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="flex flex-col gap-4 xl:col-span-2">
          {recommendations.map((rec) => (
            <RecommendationCard key={rec.id} rec={rec} />
          ))}
        </div>

        <div className="flex flex-col gap-4">
          <AiInsights />

          <Panel>
            <PanelHeader
              title="Financial health"
              description="Composite score"
            />
            <div className="p-4">
              <div className="flex items-end gap-3">
                <span className="font-mono text-4xl font-semibold tracking-tight text-foreground tabular-nums">
                  {financialHealth ? financialHealth.overall : "—"}
                </span>
                <span className="mb-1.5 text-sm text-muted-foreground">
                  / 100{financialHealth ? ` · ${healthLabel(financialHealth.overall)}` : ""}
                </span>
              </div>
              <div className="mt-4 space-y-3">
                {healthRows.map((row) => (
                  <div key={row.label}>
                    <div className="flex items-center justify-between text-[12px]">
                      <span className="text-muted-foreground">{row.label}</span>
                      <span className="font-mono font-medium text-foreground tabular-nums">
                        {row.score}
                      </span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${row.score}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </PageContainer>
  );
}
