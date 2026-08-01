"use client";

import { useState } from "react";
import { api, ApiDebtPlan } from "@/lib/api-client";
import { formatCurrency, type Account } from "@/lib/data";
import { Button } from "@/components/ui/button";
import { DialogShell } from "@/components/ui/dialog-shell";

export function DebtPlanDialog({ accounts, onClose }: { accounts: Account[]; onClose: () => void }) {
  const [strategy, setStrategy] = useState<"avalanche" | "snowball">("avalanche");
  const [extra, setExtra] = useState("0");
  const [plan, setPlan] = useState<ApiDebtPlan | null>(null);
  const [error, setError] = useState("");

  async function calculate() {
    try {
      setError("");
      setPlan(await api.simulations.debtOptimization({
        account_ids: accounts.map((account) => account.id),
        extra_monthly_payment: extra,
        strategy,
      }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to calculate payoff plan.");
    }
  }

  return (
    <DialogShell onClose={onClose} ariaLabelledBy="debt-plan-title" panelClassName="max-w-lg rounded-lg bg-card p-4">
      <h2 id="debt-plan-title" className="text-sm font-semibold">Plan debt payoff</h2>
      <p className="mt-1 text-xs text-muted-foreground">Uses current balances and saved debt terms. This comparison is not persisted.</p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <select className="h-8 rounded-md border border-border bg-background px-2 text-xs" value={strategy} onChange={(event) => setStrategy(event.target.value as typeof strategy)}>
          <option value="avalanche">Avalanche · highest APR</option>
          <option value="snowball">Snowball · smallest balance</option>
        </select>
        <input className="h-8 rounded-md border border-border bg-background px-2 text-xs" type="number" min="0" value={extra} onChange={(event) => setExtra(event.target.value)} placeholder="Extra monthly payment" />
      </div>
      {plan && (
        <div className="mt-4 rounded-md border border-border bg-muted/30 p-3 text-xs">
          <p className="font-medium">{plan.paid_off ? `Debt-free in ${plan.months_to_debt_free} months` : "Not paid off within model horizon"}</p>
          <p className="mt-1 text-muted-foreground">Estimated interest: {formatCurrency(Number(plan.total_interest_paid))}</p>
          <p className="mt-1 text-muted-foreground">Order: {plan.payoff_order.join(" → ") || "None"}</p>
          {plan.warning && <p className="mt-2 text-warning">{plan.warning}</p>}
        </div>
      )}
      {error && <p className="mt-3 text-xs text-destructive">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onClose}>Close</Button>
        <Button size="sm" onClick={() => void calculate()}>Calculate</Button>
      </div>
    </DialogShell>
  );
}
