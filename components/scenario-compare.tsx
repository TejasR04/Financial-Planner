"use client";

import { useEffect, useState } from "react";
import { Info } from "lucide-react";
import { formatCurrency } from "@/lib/data";
import { useDataRefresh, useScenariosData } from "@/lib/data-provider";
import { Panel, PanelHeader } from "@/components/panel";
import { ScenarioChart } from "@/components/charts/scenario-chart";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { displayProjectionDollars, type ProjectionDollarDisplay } from "@/lib/projection-dollars";

const metrics = [
  {
    key: "monthlyIncomeAtLifeExpectancy",
    label: "Monthly retirement income",
    hint: "Sustainable monthly withdrawal from retirement accounts, assuming a 95-year life expectancy — not the same as total net worth.",
    fmt: (v: number) => formatCurrency(v),
  },
  { key: "retirementAge", label: "Retirement age", fmt: (v: number) => `${v}` },
  {
    key: "monthlyContribution",
    label: "Monthly retirement contribution",
    fmt: (v: number) => formatCurrency(v),
  },
  {
    key: "successRate",
    label: "Monte Carlo success",
    hint: "Of 1,000 simulated trials with randomized annual returns, the percentage where retirement savings lasted through age 95 without running out — contributions stop at retirement age, then the plan's sustainable withdrawal (a % of that scenario's own balance) is taken out each year of retirement. Because the withdrawal scales with the balance, a bigger balance alone doesn't raise this number much — it mainly reflects withdrawal rate, expected return, and volatility.",
    fmt: (v: number) => `${v}%`,
  },
] as const;

export function ScenarioCompare({
  onDuplicated,
  dollarDisplay,
  currentAge,
}: {
  onDuplicated?: (newScenarioId: string) => void;
  dollarDisplay: ProjectionDollarDisplay;
  currentAge: number | null;
}) {
  const scenarios = useScenariosData();
  const refresh = useDataRefresh();
  const [active, setActive] = useState<string[]>([]);
  const [duplicateSourceId, setDuplicateSourceId] = useState<string>("");
  const [duplicating, setDuplicating] = useState(false);
  const [duplicateError, setDuplicateError] = useState<string | null>(null);

  // Scenarios load asynchronously; default every scenario to "active" the
  // first time the real list arrives, and default the duplicate-source
  // picker to the first scenario.
  useEffect(() => {
    if (scenarios.length > 0) {
      setActive(scenarios.map((s) => s.id));
      setDuplicateSourceId((prev) => (scenarios.some((s) => s.id === prev) ? prev : scenarios[0].id));
    }
  }, [scenarios]);

  const handleDuplicate = async () => {
    if (!duplicateSourceId) return;
    setDuplicating(true);
    setDuplicateError(null);
    try {
      const copy = await api.scenarios.duplicate(duplicateSourceId);
      refresh();
      onDuplicated?.(copy.id);
    } catch (err) {
      setDuplicateError(err instanceof ApiError ? err.message : "Couldn't duplicate that scenario.");
    } finally {
      setDuplicating(false);
    }
  };

  const toggle = (id: string) =>
    setActive((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <Panel className="xl:col-span-2">
        <PanelHeader
          title="Retirement balance by scenario"
          description={`Retirement accounts only · real-dollar model${dollarDisplay === "future" ? ", displayed in each year's dollars" : ", displayed in today's dollars"}`}
          actions={
            <div className="flex items-center gap-2">
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
            </div>
          }
        />
        <ScenarioChart activeIds={active} dollarDisplay={dollarDisplay} />
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
                    <span className="inline-flex items-center gap-1">
                      {m.label}
                      {"hint" in m && m.hint && (
                        <Info
                          className="size-3 shrink-0 text-muted-foreground/70"
                          aria-label={m.hint}
                        >
                          <title>{m.hint}</title>
                        </Info>
                      )}
                    </span>
                  </td>
                  {scenarios.map((s) => {
                    const value = s[m.key];
                    let formatted: string;
                    if (value === null) {
                      formatted = s.projectionStatus === "loading" ? "Loading…" : "Unavailable";
                    } else if (m.key === "monthlyIncomeAtLifeExpectancy") {
                      formatted = m.fmt(displayProjectionDollars(value, Math.max(0, s.retirementAge - (currentAge ?? s.retirementAge)), s.inflationRate, dollarDisplay));
                    } else if (m.key === "monthlyContribution" && dollarDisplay === "future") {
                      formatted = m.fmt(displayProjectionDollars(value, Math.max(0, s.retirementAge - (currentAge ?? s.retirementAge)), s.inflationRate, dollarDisplay));
                    } else {
                      formatted = m.fmt(value);
                    }
                    return (
                      <td
                        key={s.id}
                        className="px-3 py-2.5 text-right font-mono font-medium text-foreground tabular-nums"
                      >
                        {formatted}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="border-t border-border p-3">
          {scenarios.length > 1 && (
            <select
              value={duplicateSourceId}
              onChange={(e) => setDuplicateSourceId(e.target.value)}
              className="mb-2 h-8 w-full rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring"
            >
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          )}
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={handleDuplicate}
            disabled={duplicating || !duplicateSourceId}
          >
            {duplicating ? "Duplicating…" : "Duplicate & edit scenario"}
          </Button>
          {duplicateError && (
            <p className="mt-1.5 text-[11px] text-destructive">{duplicateError}</p>
          )}
        </div>
      </Panel>
    </div>
  );
}
