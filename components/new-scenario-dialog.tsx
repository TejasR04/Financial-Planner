"use client";

import { useState } from "react";
import { Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api-client";
import { useCurrentAge, useDataRefresh } from "@/lib/data-provider";

const inputClass =
  "h-9 w-full rounded-md border border-border bg-background px-2.5 text-[13px] text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-ring focus:ring-3 focus:ring-ring/20";

type Props = {
  open: boolean;
  onClose: () => void;
};

export function NewScenarioDialog({ open, onClose }: Props) {
  const currentAge = useCurrentAge();
  const refresh = useDataRefresh();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [retirementAge, setRetirementAge] = useState("65");
  const [monthlyContribution, setMonthlyContribution] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      setError(
        `Retirement age must be after your current age (${currentAge}).`,
      );
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await api.scenarios.create({
        name: name.trim(),
        description: description.trim() || undefined,
        current_age: currentAge ?? 30,
        retirement_age: retirementAgeNum,
        monthly_contribution: monthlyContribution.trim() || undefined,
      });
      refresh();
      onClose();
      setName("");
      setDescription("");
      setRetirementAge("65");
      setMonthlyContribution("");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Couldn't create that scenario. Try again.",
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
            New scenario
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

        <form onSubmit={handleSubmit} className="space-y-3 px-4 py-4">
          <div>
            <label className="mb-1 block text-[12px] font-medium text-foreground">
              Name
            </label>
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
              <label className="mb-1 block text-[12px] font-medium text-foreground">
                Retirement age
              </label>
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
                Added to your retirement balance each year — also counts toward
                total net worth, since it's new money going into your accounts.
              </p>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-[12px] font-medium text-foreground">
              Description{" "}
              <span className="text-muted-foreground">(optional)</span>
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
              Create scenario
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
