"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { Panel, PanelHeader } from "@/components/panel";
import { api, ApiError } from "@/lib/api-client";
import type { Scenario } from "@/lib/data";
import { useCurrentAge, useCurrentRetirementBalance } from "@/lib/data-provider";

type Row = { label: string; kind: string; value: number; note: string };

export function SensitivityAnalysis({ scenarios }: { scenarios: Scenario[] }) {
  const currentAge = useCurrentAge();
  const currentRetirementBalance = useCurrentRetirementBalance();

  const [scenarioId, setScenarioId] = useState<string>(scenarios[0]?.id ?? "");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Keep the selection valid as scenarios load/change/get deleted.
  useEffect(() => {
    if (scenarios.length === 0) {
      setScenarioId("");
    } else if (!scenarios.some((s) => s.id === scenarioId)) {
      setScenarioId(scenarios[0].id);
    }
  }, [scenarios, scenarioId]);

  const selectedScenario = scenarios.find((s) => s.id === scenarioId);
  // Re-fetch whenever the SELECTED scenario's own assumptions change, not
  // just when the selection itself changes — otherwise editing whichever
  // scenario is currently chosen here would keep showing stale numbers
  // until the user manually switched away and back.
  const assumptionsKey = selectedScenario
    ? `${selectedScenario.retirementAge}|${selectedScenario.monthlyContribution}|${selectedScenario.expectedReturn}`
    : "";

  useEffect(() => {
    if (!scenarioId || currentAge == null || currentRetirementBalance == null) {
      setRows(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.scenarios
      .sensitivity(scenarioId, {
        current_age: currentAge,
        current_retirement_balance: String(currentRetirementBalance),
      })
      .then((res) => {
        if (cancelled) return;
        setRows(res.rows.map((r) => ({ label: r.label, kind: r.kind, value: parseFloat(r.value), note: r.note })));
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Couldn't compute sensitivity analysis.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scenarioId, currentAge, currentRetirementBalance, assumptionsKey]);

  return (
    <Panel className="xl:col-span-2">
      <PanelHeader
        title="Sensitivity analysis"
        description={
          selectedScenario
            ? `How each input moves ${selectedScenario.name}'s projected outcome — computed live, not illustrative`
            : "How each input moves the projected outcome"
        }
        actions={
          scenarios.length > 1 ? (
            <select
              value={scenarioId}
              onChange={(e) => setScenarioId(e.target.value)}
              className="h-7 rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring"
            >
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          ) : null
        }
      />
      <div className="p-4">
        {scenarios.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-muted-foreground">
            Create a scenario to see how each assumption affects its projection.
          </p>
        ) : loading ? (
          <div className="flex items-center justify-center gap-2 py-8 text-[13px] text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Computing…
          </div>
        ) : error ? (
          <p className="py-6 text-center text-[13px] text-destructive">{error}</p>
        ) : (
          <div className="space-y-3">
            {rows?.map((row) => {
              const pos = row.value >= 0;
              const isSuccessMetric = row.kind === "success_pp";
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
                        width: `${Math.min(Math.abs(row.value) * 3, 46)}%`,
                      }}
                    />
                  </div>
                  <span
                    className={`w-16 shrink-0 text-right font-mono text-[13px] font-medium tabular-nums ${pos ? "text-positive" : "text-destructive"}`}
                  >
                    {pos ? "+" : ""}
                    {row.value}
                    {isSuccessMetric ? "pp" : "%"}
                  </span>
                  <span className="hidden w-40 shrink-0 text-right text-[11px] text-muted-foreground lg:block">
                    {row.note}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Panel>
  );
}
