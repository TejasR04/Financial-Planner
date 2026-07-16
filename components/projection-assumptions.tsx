"use client";

import { useState } from "react";
import { Panel, PanelHeader } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/data";

type Assumption = {
  key: string;
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  suffix: string;
};

const initial: Assumption[] = [
  {
    key: "age",
    label: "Target retirement age",
    min: 45,
    max: 70,
    step: 1,
    value: 62,
    suffix: "yrs",
  },
  {
    key: "save",
    label: "Savings rate",
    min: 10,
    max: 60,
    step: 1,
    value: 35,
    suffix: "%",
  },
  {
    key: "return",
    label: "Expected real return",
    min: 2,
    max: 10,
    step: 0.1,
    value: 6.5,
    suffix: "%",
  },
  {
    key: "inflation",
    label: "Inflation",
    min: 1,
    max: 6,
    step: 0.1,
    value: 2.8,
    suffix: "%",
  },
  {
    key: "withdraw",
    label: "Withdrawal rate",
    min: 2.5,
    max: 5,
    step: 0.05,
    value: 3.5,
    suffix: "%",
  },
];

export function ProjectionAssumptions() {
  const [assumptions, setAssumptions] = useState(initial);

  const update = (key: string, value: number) =>
    setAssumptions((prev) =>
      prev.map((a) => (a.key === key ? { ...a, value } : a)),
    );

  // Simple deterministic projection derived from the sliders.
  const save = assumptions.find((a) => a.key === "save")!.value;
  const ret = assumptions.find((a) => a.key === "return")!.value;
  const age = assumptions.find((a) => a.key === "age")!.value;
  const years = age - 33;
  const annualContribution = 190000 * (save / 100);
  const fv =
    1284920 * Math.pow(1 + ret / 100, years) +
    annualContribution * ((Math.pow(1 + ret / 100, years) - 1) / (ret / 100));

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
                {a.value}
                <span className="ml-0.5 text-muted-foreground">{a.suffix}</span>
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
          {formatCurrency(fv, { compact: true })}
        </p>
        <p className="mt-0.5 text-[11px] text-muted-foreground">
          Over {years} years · {formatCurrency(annualContribution)}/yr
          contributed
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
