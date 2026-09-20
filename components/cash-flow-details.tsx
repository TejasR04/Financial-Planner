"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { groupBudgetCashFlowTransactions } from "@/lib/budget-cash-flow";
import { formatCurrency } from "@/lib/data";
import { useDataGeneration } from "@/lib/data-provider";
import { DialogShell } from "./ui/dialog-shell";
import { Button } from "./ui/button";

export function CashFlowDetails({ month, direction, onClose }: {
  month: string;
  direction: "inflow" | "outflow";
  onClose: () => void;
}) {
  const generation = useDataGeneration();
  const [groups, setGroups] = useState<ReturnType<typeof groupBudgetCashFlowTransactions>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [year, monthNumber] = month.split("-").map(Number);
  const label = new Date(year, monthNumber - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
  const title = `${label} ${direction === "outflow" ? "budget expenses" : "income"}`;

  useEffect(() => {
    let current = true;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setGroups([]);
    Promise.all([
      api.transactions.listAll({ since: `${month}-01`, until: `${month}-${new Date(year, monthNumber, 0).getDate()}` }, controller.signal),
      api.budgets.categories(controller.signal),
    ]).then(([transactions, categories]) => {
      if (!current) return;
      setGroups(groupBudgetCashFlowTransactions(transactions, direction,
        new Set(categories.filter((category) => category.active).map((category) => category.id))));
    }).catch((err) => {
      if (current) setError(err instanceof Error ? err.message : "Couldn't load this month's transactions.");
    }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [month, year, monthNumber, direction, generation, retry]);

  return <DialogShell onClose={onClose} ariaLabel={title} panelClassName="max-w-3xl p-5">
    <div className="flex items-start justify-between gap-4">
      <div>
        <h2 className="text-base font-semibold">{title}</h2>
        <p className="mt-1 text-xs text-muted-foreground">{direction === "outflow"
          ? "Assigned budget expenses and transfers, net of refunds and reimbursements. Pending transactions are included; ignored activity is excluded."
          : "Positive income outside budget categories, such as paychecks and interest. Transfers and reimbursements are excluded."}</p>
      </div>
      <Button size="sm" variant="outline" onClick={onClose}>Close</Button>
    </div>
    {loading ? <p role="status" className="py-6 text-sm">Loading transactions…</p>
      : error ? <div className="py-6"><p role="alert" className="text-sm text-destructive">{error}</p><Button className="mt-3" size="sm" onClick={() => setRetry((value) => value + 1)}>Retry</Button></div>
      : <>
        <p className="my-4 text-sm font-semibold">{direction === "outflow" ? "Net budget expenses" : "Total income"}: {formatCurrency(groups.reduce((sum, group) => sum + group.total, 0))}</p>
        {groups.length === 0 && <p className="py-4 text-sm text-muted-foreground">No matching transactions this month.</p>}
        {groups.map((group) => <section key={group.id} className="mt-4 rounded-lg border border-border">
          <div className="flex justify-between gap-3 bg-muted/40 px-3 py-2 text-sm font-medium"><h3>{group.name}</h3><span>{formatCurrency(group.total)}</span></div>
          <div className="overflow-x-auto"><table className="w-full text-left text-xs">
            <thead><tr className="border-b border-border text-muted-foreground"><th className="p-3">Date</th><th className="p-3">Transaction</th><th className="p-3">Account</th><th className="p-3 text-right">Money in / out</th></tr></thead>
            <tbody>{group.transactions.map((transaction) => <tr key={transaction.id} className="border-b border-border last:border-0">
              <td className="whitespace-nowrap p-3">{new Date(`${transaction.posted_at}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</td>
              <td className="p-3">{transaction.merchant}{transaction.status === "pending" && <span className="ml-2 text-muted-foreground">Pending</span>}</td>
              <td className="p-3">{transaction.account_name ?? "Account"}</td>
              <td className="whitespace-nowrap p-3 text-right tabular-nums">{formatCurrency(Number(transaction.amount), { sign: true })}</td>
            </tr>)}</tbody>
          </table></div>
        </section>)}
      </>}
  </DialogShell>;
}
