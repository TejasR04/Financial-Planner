"use client";

import { Plus, Sparkles } from "lucide-react";
import { PageContainer, PageHeader } from "@/components/page-container";
import { ScenarioCompare } from "@/components/scenario-compare";
import { ProjectionAssumptions } from "@/components/projection-assumptions";
import { Panel, PanelHeader } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatCurrency } from "@/lib/data";
import { useScenariosData } from "@/lib/data-provider";

export default function ProjectionsPage() {
  const scenarios = useScenariosData();
  const best =
    scenarios.length > 0
      ? scenarios.reduce((a, b) => (b.successRate > a.successRate ? b : a))
      : null;

  return (
    <PageContainer>
      <PageHeader
        title="Projections"
        description="Monte Carlo modeling across savings, allocation, and retirement scenarios"
        actions={
          <>
            <Button variant="outline" size="sm">
              <Sparkles />
              Optimize
            </Button>
            <Button size="sm">
              <Plus />
              New scenario
            </Button>
          </>
        }
      />

      {/* Scenario summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {scenarios.map((s) => (
          <div
            key={s.id}
            className="flex flex-col rounded-lg border border-border bg-card p-4"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className="size-2.5 rounded-[3px]"
                  style={{ background: s.color }}
                />
                <span className="text-[13px] font-semibold text-foreground">
                  {s.name}
                </span>
              </div>
              {s.id === best?.id && (
                <Badge variant="positive">Recommended</Badge>
              )}
            </div>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground text-pretty">
              {s.description}
            </p>
            <div className="mt-3 flex items-end justify-between border-t border-border pt-3">
              <div>
                <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  Net worth at 65
                </p>
                <p className="font-mono text-lg font-semibold text-foreground tabular-nums">
                  {formatCurrency(s.netWorthAt65, { compact: true })}
                </p>
              </div>
              <div className="text-right">
                <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  Success
                </p>
                <p className="font-mono text-lg font-semibold text-primary tabular-nums">
                  {s.successRate}%
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Comparison */}
      <div className="mt-4">
        <ScenarioCompare />
      </div>

      {/* Assumptions + notes */}
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="xl:col-span-1">
          <ProjectionAssumptions />
        </div>

        <Panel className="xl:col-span-2">
          <PanelHeader
            title="Sensitivity analysis"
            description="How each input moves the projected outcome"
          />
          <div className="p-4">
            <div className="space-y-3">
              {[
                {
                  label: "+1% savings rate",
                  delta: 4.1,
                  note: "$248K by age 65",
                },
                {
                  label: "+1% real return",
                  delta: 12.6,
                  note: "$770K by age 65",
                },
                {
                  label: "-2 years to retirement",
                  delta: -8.3,
                  note: "$505K less accrued",
                },
                {
                  label: "+0.5% withdrawal rate",
                  delta: -5.4,
                  note: "Success falls to 79%",
                },
                {
                  label: "Max tax-advantaged space",
                  delta: 6.2,
                  note: "$378K + tax savings",
                },
              ].map((row) => {
                const pos = row.delta >= 0;
                return (
                  <div key={row.label} className="flex items-center gap-3">
                    <span className="w-48 shrink-0 text-[13px] text-foreground">
                      {row.label}
                    </span>
                    <div className="relative flex h-6 flex-1 items-center">
                      <div className="absolute left-1/2 h-full w-px bg-border" />
                      <div
                        className={`absolute h-2.5 rounded-[2px] ${pos ? "left-1/2 bg-positive" : "right-1/2 bg-destructive"}`}
                        style={{
                          width: `${Math.min(Math.abs(row.delta) * 3, 46)}%`,
                        }}
                      />
                    </div>
                    <span
                      className={`w-14 shrink-0 text-right font-mono text-[13px] font-medium tabular-nums ${pos ? "text-positive" : "text-destructive"}`}
                    >
                      {pos ? "+" : ""}
                      {row.delta}%
                    </span>
                    <span className="hidden w-40 shrink-0 text-right text-[11px] text-muted-foreground lg:block">
                      {row.note}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </Panel>
      </div>
    </PageContainer>
  );
}
