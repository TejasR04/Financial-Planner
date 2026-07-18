"use client";

import { useEffect, useState } from "react";
import { Panel, PanelHeader } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/data";
import { useProfileSummary } from "@/lib/data-provider";
import { api, ApiError } from "@/lib/api-client";

type Assumption = {
  key: "age" | "contribution" | "return";
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  suffix: string;
};

const FALLBACK_ASSUMPTIONS: Assumption[] = [
  { key: "age", label: "Target retirement age", min: 45, max: 75, step: 1, value: 65, suffix: "yrs" },
  { key: "contribution", label: "Monthly contribution", min: 0, max: 10000, step: 100, value: 500, suffix: "$" },
  { key: "return", label: "Expected real return", min: 2, max: 10, step: 0.1, value: 6.5, suffix: "%" },
];

export function ProjectionAssumptions() {
  const profile = useProfileSummary();
  const [assumptions, setAssumptions] = useState<Assumption[]>(FALLBACK_ASSUMPTIONS);
  const [initialized, setInitialized] = useState(false);
  const [result, setResult] = useState<{ fv: number; years: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Seed sliders from the user's real profile + cash-flow-derived surplus
  // the first time it becomes available, rather than a hardcoded salary.
  useEffect(() => {
    if (!profile || initialized) return;
    setAssumptions([
      {
        key: "age",
        label: "Target retirement age",
        min: profile.currentAge + 1,
        max: 80,
        step: 1,
        value: profile.targetRetirementAge,
        suffix: "yrs",
      },
      {
        key: "contribution",
        label: "Monthly contribution",
        min: 0,
        max: 10000,
        step: 100,
        value: profile.monthlySurplusEstimate,
        suffix: "$",
      },
      {
        key: "return",
        label: "Expected real return",
        min: 2,
        max: 10,
        step: 0.1,
        value: Math.round(parseFloat(profile.expectedReturn) * 1000) / 10,
        suffix: "%",
      },
    ]);
    setInitialized(true);
  }, [profile, initialized]);

  const update = (key: string, value: number) =>
    setAssumptions((prev) =>
      prev.map((a) => (a.key === key ? { ...a, value } : a)),
    );

  const age = assumptions.find((a) => a.key === "age")!.value;
  const contribution = assumptions.find((a) => a.key === "contribution")!.value;
  const ret = assumptions.find((a) => a.key === "return")!.value;
  const years = Math.max(1, Math.round(age - (profile?.currentAge ?? age - 30)));

  // Debounced call to the real simulation endpoint — this replaces the old
  // hardcoded-salary compound-interest formula (ARCHITECTURE.md §11).
  useEffect(() => {
    if (!profile) return;
    const handle = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const sim = await api.simulations.netWorth({
          current_age: profile.currentAge,
          retirement_age: age,
          years,
          expected_return: String(ret / 100),
          annual_net_contribution: String(contribution * 12),
        });
        setResult({ fv: parseFloat(sim.projected_net_worth_at_horizon), years });
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Couldn't run the projection.");
      } finally {
        setLoading(false);
      }
    }, 400);
    return () => clearTimeout(handle);
  }, [profile, age, contribution, ret, years]);

  return (
    <Panel>
      <PanelHeader
        title="Model assumptions"
        description="Adjust inputs to reshape the projection"
      />
      <div className="flex flex-col gap-4 p-4">
        {assumptions.map((a) => (
          <div key={a.key}>
            <div className="flex items-center justify-between">
              <label htmlFor={a.key} className="text-[13px] text-foreground">
                {a.label}
              </label>
              <span className="font-mono text-[13px] font-medium text-foreground tabular-nums">
                {a.suffix === "$" ? formatCurrency(a.value) : a.value}
                {a.suffix !== "$" && (
                  <span className="ml-0.5 text-muted-foreground">{a.suffix}</span>
                )}
              </span>
            </div>
            <input
              id={a.key}
              type="range"
              min={a.min}
              max={a.max}
              step={a.step}
              value={a.value}
              onChange={(e) => update(a.key, Number(e.target.value))}
              className="mt-2 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-muted accent-primary"
            />
          </div>
        ))}
      </div>

      <div className="border-t border-border bg-muted/30 px-4 py-3.5">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Projected net worth at retirement
        </p>
        <p className="mt-1 font-mono text-2xl font-semibold tracking-tight text-primary tabular-nums">
          {result ? formatCurrency(result.fv, { compact: true }) : loading ? "…" : "—"}
        </p>
        <p className="mt-0.5 text-[11px] text-muted-foreground">
          {error
            ? error
            : `Over ${years} years · ${formatCurrency(contribution * 12)}/yr contributed`}
        </p>
      </div>
      <div className="border-t border-border p-3">
        <Button size="sm" className="w-full">
          Save as scenario
        </Button>
      </div>
    </Panel>
  );
}
