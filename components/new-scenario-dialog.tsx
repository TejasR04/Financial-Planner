"use client";

import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api-client";
import type { Scenario } from "@/lib/data";
import { useCurrentAge, useCurrentRetirementBalance, useDataRefresh } from "@/lib/data-provider";

const inputClass =
  "h-9 w-full rounded-md border border-border bg-background px-2.5 text-[13px] text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-ring focus:ring-3 focus:ring-ring/20";

type Props = {
  open: boolean;
  onClose: () => void;
  /** When provided, the dialog edits this scenario (PATCH) instead of
   * creating a new one (POST). */
  scenario?: Scenario | null;
};

const DEFAULT_RETIREMENT_AGE = "65";
const DEFAULT_EXPECTED_RETURN = "6.5";

export function NewScenarioDialog({ open, onClose, scenario = null }: Props) {
  const currentAge = useCurrentAge();
  const currentRetirementBalance = useCurrentRetirementBalance();
  const refresh = useDataRefresh();
  const isEditing = scenario != null;

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [retirementAge, setRetirementAge] = useState(DEFAULT_RETIREMENT_AGE);
  const [monthlyContribution, setMonthlyContribution] = useState("");
  const [expectedReturn, setExpectedReturn] = useState(DEFAULT_EXPECTED_RETURN);
  const [useIncomeTarget, setUseIncomeTarget] = useState(false);
  const [desiredIncome, setDesiredIncome] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset/prefill whenever the dialog opens or which scenario it's editing
  // changes, so stale values from a previous open don't leak in.
  useEffect(() => {
    if (!open) return;
    if (scenario) {
      setName(scenario.name);
      setDescription(scenario.description ?? "");
      setRetirementAge(String(scenario.retirementAge));
      setMonthlyContribution(scenario.monthlyContribution ? String(scenario.monthlyContribution) : "");
      setExpectedReturn(String(Math.round(scenario.expectedReturn * 1000) / 10));
      setUseIncomeTarget(scenario.desiredMonthlyIncomeToday != null);
      setDesiredIncome(
        scenario.desiredMonthlyIncomeToday != null ? String(scenario.desiredMonthlyIncomeToday) : "",
      );
    } else {
      setName("");
      setDescription("");
      setRetirementAge(DEFAULT_RETIREMENT_AGE);
      setMonthlyContribution("");
      setExpectedReturn(DEFAULT_EXPECTED_RETURN);
      setUseIncomeTarget(false);
      setDesiredIncome("");
    }
    setError(null);
  }, [open, scenario]);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Give the scenario a name.");
      return;
    }
    const retirementAgeNum = Number(retirementAge);
    if (!Number.isFinite(retirementAgeNum) || retirementAgeNum <= 0) {
      setError("Retirement age must be a positive number.");
      return;
    }
    if (currentAge != null && retirementAgeNum <= currentAge) {
      setError(`Retirement age must be after your current age (${currentAge}).`);
      return;
    }
    const expectedReturnNum = Number(expectedReturn);
    if (!Number.isFinite(expectedReturnNum) || expectedReturnNum < 0 || expectedReturnNum > 20) {
      setError("Expected real return should be a percentage between 0 and 20.");
      return;
    }
    let desiredIncomeNum: number | null = null;
    if (useIncomeTarget) {
      desiredIncomeNum = Number(desiredIncome);
      if (!Number.isFinite(desiredIncomeNum) || desiredIncomeNum <= 0) {
        setError("Enter a monthly income target greater than 0, or turn the target off.");
        return;
      }
    }

    setSubmitting(true);
    setError(null);
    try {
      if (isEditing && scenario) {
        const wasTargetSet = scenario.desiredMonthlyIncomeToday != null;
        await api.scenarios.update(scenario.id, {
          name: name.trim(),
          description: description.trim(),
          retirement_age: retirementAgeNum,
          monthly_contribution: monthlyContribution.trim() || "0",
          expected_return: (expectedReturnNum / 100).toFixed(4),
          ...(useIncomeTarget
            ? { desired_monthly_income_today: String(desiredIncomeNum) }
            : wasTargetSet
              ? { clear_income_target: true }
              : {}),
        });
        // The dashboard reuses the scenario's most recent run rather than
        // re-simulating on every page load (Monte Carlo isn't free) — so
        // without this, editing a scenario would silently keep showing
        // the OLD chart/sensitivity numbers from before the edit.
        if (currentAge != null && currentRetirementBalance != null) {
          await api.scenarios.run(scenario.id, {
            current_age: currentAge,
            current_retirement_balance: String(currentRetirementBalance),
            include_monte_carlo: true,
            monte_carlo_trials: 1000,
          });
        }
      } else {
        await api.scenarios.create({
          name: name.trim(),
          description: description.trim() || undefined,
          current_age: currentAge ?? 30,
          retirement_age: retirementAgeNum,
          monthly_contribution: monthlyContribution.trim() || undefined,
          expected_return: (expectedReturnNum / 100).toFixed(4),
          desired_monthly_income_today: useIncomeTarget ? String(desiredIncomeNum) : undefined,
        });
      }
      refresh();
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : `Couldn't ${isEditing ? "save" : "create"} that scenario. Try again.`,
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-lg border border-border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-[13px] font-semibold text-foreground">
            {isEditing ? "Edit scenario" : "New scenario"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="max-h-[80vh] space-y-3 overflow-y-auto px-4 py-4">
          <div>
            <label className="mb-1 block text-[12px] font-medium text-foreground">Name</label>
            <input
              className={inputClass}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Retire at 60"
              autoFocus
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-[12px] font-medium text-foreground">Retirement age</label>
              <input
                className={inputClass}
                type="number"
                min={1}
                value={retirementAge}
                onChange={(e) => setRetirementAge(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-medium text-foreground">
                Expected real return
              </label>
              <input
                className={inputClass}
                type="number"
                min={0}
                max={20}
                step="0.1"
                value={expectedReturn}
                onChange={(e) => setExpectedReturn(e.target.value)}
              />
              <p className="mt-1 text-[11px] text-muted-foreground">Annual %, e.g. 6.5</p>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-[12px] font-medium text-foreground">
              Monthly retirement contribution
            </label>
            <input
              className={inputClass}
              type="number"
              min={0}
              step="0.01"
              value={monthlyContribution}
              onChange={(e) => setMonthlyContribution(e.target.value)}
              placeholder="0"
            />
            <p className="mt-1 text-[11px] text-muted-foreground">
              Added to your retirement balance each year — also counts toward total net worth,
              since it's new money going into your accounts.
            </p>
          </div>

          <div className="rounded-md border border-border p-3">
            <label className="flex items-center gap-2 text-[12px] font-medium text-foreground">
              <input
                type="checkbox"
                checked={useIncomeTarget}
                onChange={(e) => setUseIncomeTarget(e.target.checked)}
                className="size-3.5 rounded border-border"
              />
              Target a specific retirement income
            </label>
            {useIncomeTarget ? (
              <div className="mt-2">
                <label className="mb-1 block text-[12px] font-medium text-foreground">
                  Desired monthly income, in today&apos;s dollars
                </label>
                <input
                  className={inputClass}
                  type="number"
                  min={0}
                  step="1"
                  value={desiredIncome}
                  onChange={(e) => setDesiredIncome(e.target.value)}
                  placeholder="e.g. 5000"
                />
                <p className="mt-1 text-[11px] text-muted-foreground">
                  What this amount could buy today. We&apos;ll inflate it forward to the actual
                  nominal dollars you&apos;ll need at retirement, and keep escalating it with
                  inflation every year of retirement so your purchasing power stays constant —
                  this replaces the standard withdrawal-rate calculation for this scenario.
                </p>
              </div>
            ) : (
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                Off: this scenario uses the standard 4%-of-balance withdrawal rule instead.
              </p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-[12px] font-medium text-foreground">
              Description <span className="text-muted-foreground">(optional)</span>
            </label>
            <textarea
              className={`${inputClass} h-16 resize-none py-2`}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What's different about this scenario?"
            />
          </div>

          {error && <p className="text-xs text-destructive">{error}</p>}

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? <Loader2 className="animate-spin" /> : null}
              {isEditing ? "Save changes" : "Create scenario"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
