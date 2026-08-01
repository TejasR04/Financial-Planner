"use client";

import { useEffect, useState } from "react";
import { Panel, PanelHeader } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/data";
import { useCurrentRetirementBalance, useDataRefresh, useProfileSummary } from "@/lib/data-provider";
import { api, ApiError } from "@/lib/api-client";
import { displayProjectionDollars, type ProjectionDollarDisplay } from "@/lib/projection-dollars";

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
  { key: "contribution", label: "Monthly savings contribution", min: 0, max: 10000, step: 100, value: 500, suffix: "$" },
  { key: "return", label: "Expected real return", min: 2, max: 10, step: 0.1, value: 6.5, suffix: "%" },
];

export function ProjectionAssumptions({ dollarDisplay }: { dollarDisplay: ProjectionDollarDisplay }) {
  const profile = useProfileSummary();
  const refresh = useDataRefresh();
  const [assumptions, setAssumptions] = useState<Assumption[]>(FALLBACK_ASSUMPTIONS);
  const [initialized, setInitialized] = useState(false);
  const retirementBalance = useCurrentRetirementBalance();
  const [result, setResult] = useState<{ balanceAtRetirement: number; monthlyIncome: number; years: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

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
        label: "Monthly savings contribution",
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

  const update = (key: string, value: number) => {
    setAssumptions((prev) =>
      prev.map((a) => (a.key === key ? { ...a, value } : a)),
    );
    setSaved(false);
    setSaveError(null);
  };

  const age = assumptions.find((a) => a.key === "age")!.value;
  const contribution = assumptions.find((a) => a.key === "contribution")!.value;
  const ret = assumptions.find((a) => a.key === "return")!.value;
  const years = Math.max(1, Math.round(age - (profile?.currentAge ?? age - 30)));

  const handleSaveAsScenario = async () => {
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      await api.scenarios.create({
        name: `Retire at ${age}`,
        current_age: profile?.currentAge ?? age - 30,
        retirement_age: age,
        monthly_contribution: String(contribution),
        expected_return: (ret / 100).toFixed(4),
      });
      refresh();
      setSaved(true);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Couldn't save that scenario.");
    } finally {
      setSaving(false);
    }
  };

  // Debounced retirement calculation. This deliberately uses retirement
  // assets, not total net worth: a home or taxable cash balance alone does
  // not represent spendable retirement income in this model.
  useEffect(() => {
    if (!profile || retirementBalance == null) return;
    let cancelled = false;
    const handle = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const sim = await api.simulations.retirement({
          current_age: profile.currentAge,
          retirement_age: age,
          current_retirement_balance: String(retirementBalance),
          expected_return: String(ret / 100),
          annual_contribution: String(contribution * 12),
        });
        if (!cancelled) {
          setResult({
            balanceAtRetirement: parseFloat(sim.projected_balance_at_retirement),
            monthlyIncome: parseFloat(sim.monthly_sustainable_withdrawal),
            years: sim.years_to_retirement,
          });
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Couldn't run the projection.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [profile, retirementBalance, age, contribution, ret, years]);

  return (
    <Panel>
      <PanelHeader
        title="Model assumptions"
        description="Quick retirement-balance what-if — contributions stop at retirement, then withdrawals begin"
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
              className="mt-2 h-2 w-full cursor-pointer appearance-none rounded-full border border-primary/30 bg-primary/15 accent-primary shadow-inner outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 [&::-moz-range-track]:h-2 [&::-moz-range-track]:rounded-full [&::-moz-range-track]:bg-primary/20 [&::-moz-range-thumb]:size-4 [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-background [&::-moz-range-thumb]:bg-primary [&::-webkit-slider-runnable-track]:h-2 [&::-webkit-slider-runnable-track]:rounded-full [&::-webkit-slider-runnable-track]:bg-primary/20 [&::-webkit-slider-thumb]:mt-[-5px] [&::-webkit-slider-thumb]:size-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-background [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:shadow-sm"
            />
          </div>
        ))}
      </div>

      <div className="border-t border-border bg-muted/30 px-4 py-3.5">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Retirement balance at age {age}
        </p>
        <p className="mt-1 font-mono text-2xl font-semibold tracking-tight text-primary tabular-nums">
          {result ? formatCurrency(displayProjectionDollars(result.balanceAtRetirement, years, Number(profile?.inflationRate ?? 0), dollarDisplay), { compact: true }) : loading ? "…" : "—"}
        </p>
        <p className="mt-0.5 text-[11px] text-muted-foreground">
          {error
            ? error
            : result
              ? `${formatCurrency(displayProjectionDollars(result.monthlyIncome, years, Number(profile?.inflationRate ?? 0), dollarDisplay))}/mo sustainable withdrawal · ${formatCurrency(contribution * 12)}/yr contributed`
              : `Over ${years} years · ${formatCurrency(contribution * 12)}/yr contributed`}
        </p>
      </div>
      <div className="border-t border-border p-3">
        <Button size="sm" className="w-full" onClick={handleSaveAsScenario} disabled={saving}>
          {saving ? "Saving…" : saved ? "Saved as scenario ✓" : "Save as scenario"}
        </Button>
        {saveError && <p className="mt-1.5 text-[11px] text-destructive">{saveError}</p>}
      </div>
    </Panel>
  );
}
