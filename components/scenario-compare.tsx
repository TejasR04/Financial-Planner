"use client";

import { useState } from "react";
import { scenarios, formatCurrency } from "@/lib/data";
import { Panel, PanelHeader } from "@/components/panel";
import { ScenarioChart } from "@/components/charts/scenario-chart";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const metrics = [
  {
    key: "netWorthAt65",
    label: "Net worth at 65",
    fmt: (v: number) => formatCurrency(v, { compact: true }),
  },
  { key: "retirementAge", label: "Retirement age", fmt: (v: number) => `${v}` },
  {
    key: "monthlyContribution",
    label: "Monthly contribution",
    fmt: (v: number) => formatCurrency(v),
  },
  {
    key: "successRate",
    label: "Monte Carlo success",
    fmt: (v: number) => `${v}%`,
  },
] as const;

export function ScenarioCompare() {
  const [active, setActive] = useState<string[]>(scenarios.map((s) => s.id));

  const toggle = (id: string) =>
    setActive((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <Panel className="xl:col-span-2">
        <PanelHeader
          title="Projected net worth by scenario"
          description="Modeled to age 65 · nominal dollars"
          actions={
            <div className="flex items-center gap-1">
              {scenarios.map((s) => {
                const on = active.includes(s.id);
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => toggle(s.id)}
                    className={cn(
                      "flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors",
                      on
                        ? "border-border bg-muted text-foreground"
                        : "border-transparent text-muted-foreground hover:bg-muted/50",
                    )}
                  >
                    <span
                      className="size-2 rounded-[2px]"
                      style={{ background: s.color, opacity: on ? 1 : 0.4 }}
                    />
                    {s.name}
                  </button>
                );
              })}
            </div>
          }
        />
        <ScenarioChart activeIds={active} />
      </Panel>

      <Panel>
        <PanelHeader
          title="Scenario metrics"
          description="Side-by-side comparison"
        />
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-border">
                <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Metric
                </th>
                {scenarios.map((s) => (
                  <th key={s.id} className="px-3 py-2 text-right">
                    <span className="flex items-center justify-end gap-1.5 text-[11px] font-medium text-foreground">
                      <span
                        className="size-2 rounded-[2px]"
                        style={{ background: s.color }}
                      />
                      {s.name}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.map((m) => (
                <tr
                  key={m.key}
                  className="border-b border-border/60 last:border-0"
                >
                  <td className="px-4 py-2.5 text-muted-foreground">
                    {m.label}
                  </td>
                  {scenarios.map((s) => (
                    <td
                      key={s.id}
                      className="px-3 py-2.5 text-right font-mono font-medium text-foreground tabular-nums"
                    >
                      {m.fmt(s[m.key] as number)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="border-t border-border p-3">
          <Button variant="outline" size="sm" className="w-full">
            Duplicate &amp; edit scenario
          </Button>
        </div>
      </Panel>
    </div>
  );
}
