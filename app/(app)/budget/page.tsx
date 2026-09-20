"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, ChevronLeft, ChevronRight, Plus, Tag, Trash2 } from "lucide-react";
import { PageContainer, PageHeader } from "@/components/page-container";
import { Panel, PanelHeader } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { DialogShell } from "@/components/ui/dialog-shell";
import {
  api,
  ApiError,
  type ApiBudgetCategory,
  type ApiBudgetSummary,
  type ApiUncategorizedBudgetTransaction,
} from "@/lib/api-client";
import { formatCurrency } from "@/lib/data";
import { localMonthKey } from "@/lib/local-date";
import { SpendingPaceChart } from "@/components/charts/spending-pace-chart";
import { BudgetBreakdown } from "@/components/budget-breakdown";
import { useDataRefresh } from "@/lib/data-provider";


function shiftMonth(value: string, amount: number) {
  const [year, month] = value.split("-").map(Number);
  const date = new Date(year, month - 1 + amount, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function formatMonth(value: string) {
  const [year, month] = value.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

type PendingAssignment = {
  transaction: ApiUncategorizedBudgetTransaction;
  categoryId?: string;
  transactionType?: "income" | "transfer" | "credit_card_payment";
  treatmentName: string;
};

export default function BudgetPage() {
  const router = useRouter();
  const refreshData = useDataRefresh();
  const [month, setMonth] = useState(() => localMonthKey());
  const [summary, setSummary] = useState<ApiBudgetSummary | null>(null);
  const [categories, setCategories] = useState<ApiBudgetCategory[]>([]);
  const [uncategorized, setUncategorized] = useState<ApiUncategorizedBudgetTransaction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [categoryName, setCategoryName] = useState("");
  const [groupName, setGroupName] = useState("Other");
  const [limit, setLimit] = useState("");
  const [pendingAssignment, setPendingAssignment] = useState<PendingAssignment | null>(null);
  const [assigning, setAssigning] = useState(false);
  const [categoryOrder, setCategoryOrder] = useState("over");
  const requestGeneration = useRef(0);
  const monthRef = useRef(month);
  const summaryMonthRef = useRef(month);

  useEffect(() => {
    monthRef.current = month;
  }, [month]);

  const activeCategories = useMemo(() => categories.filter((category) => category.active), [categories]);
  const chartData = useMemo(
    () => (summary?.categories ?? []).map((item) => ({
      name: item.name,
      budgeted: Number(item.budgeted),
      spent: Number(item.spent) + Number(item.pending),
    })),
    [summary],
  );
  const totalBudgeted = chartData.reduce((sum, item) => sum + item.budgeted, 0);
  const totalSpent = chartData.reduce((sum, item) => sum + item.spent, 0);
  const unassignedSpent = Number(summary?.uncategorized.spent ?? 0) + Number(summary?.uncategorized.pending ?? 0);
  const allSpent = totalSpent + unassignedSpent;
  const queuePosted = uncategorized.filter((row) => row.status === "cleared").reduce((sum, row) => sum + Math.abs(Number(row.amount)), 0);
  const queuePending = uncategorized.filter((row) => row.status === "pending").reduce((sum, row) => sum + Math.abs(Number(row.amount)), 0);
  const orderedCategories = useMemo(() => {
    const rows = [...(summary?.categories ?? [])];
    if (categoryOrder === "over") rows.sort((a, b) => Number(a.remaining) - Number(b.remaining));
    if (categoryOrder === "group") rows.sort((a, b) => {
      const groups = ["Needs", "Wants", "Other"];
      const rank = (group: string) => groups.includes(group) ? groups.indexOf(group) : 3;
      return rank(a.group_name) - rank(b.group_name) || a.group_name.localeCompare(b.group_name) || a.name.localeCompare(b.name);
    });
    return rows;
  }, [summary, categoryOrder]);

  const reload = useCallback(async (signal?: AbortSignal, requestedMonth = monthRef.current) => {
    const generation = ++requestGeneration.current;
    setLoading(true);
    setError(null);
    if (requestedMonth !== summaryMonthRef.current) setSummary(null);
    try {
      const [nextSummary, nextCategories, nextUncategorized] = await Promise.all([
        api.budgets.summary(requestedMonth, signal),
        api.budgets.categories(signal),
        api.budgets.reviewQueue(signal),
      ]);
      if (requestGeneration.current !== generation) return;
      setSummary(nextSummary);
      summaryMonthRef.current = requestedMonth;
      setCategories(nextCategories);
      setUncategorized(nextUncategorized);
    } catch (err) {
      if (signal?.aborted || requestGeneration.current !== generation) return;
      setError(err instanceof ApiError ? err.message : "Couldn't load your budget.");
    } finally {
      if (requestGeneration.current === generation) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void reload(controller.signal, month);
    return () => controller.abort();
  }, [month, reload]);

  const createCategory = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await api.budgets.createCategory({ name: categoryName, group_name: groupName, monthly_limit: limit || "0" });
      setCategoryName("");
      setLimit("");
      await reload();
      refreshData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create the category.");
    }
  };

  const updateLimit = async (categoryId: string, monthlyLimit: string) => {
    if (!monthlyLimit || Number.isNaN(Number(monthlyLimit)) || Number(monthlyLimit) < 0) return;
    try {
      await api.budgets.updateCategory(categoryId, { monthly_limit: monthlyLimit });
      await reload();
      refreshData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't update the monthly budget.");
    }
  };

  const deleteCategory = async (category: ApiBudgetCategory) => {
    if (!window.confirm(`Delete ${category.name}? Assigned transactions will become uncategorized and its merchant rules will be removed.`)) return;
    setError(null);
    try {
      await api.budgets.deleteCategory(category.id);
      await reload();
      refreshData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't delete the category.");
    }
  };

  const requestAssignment = (transaction: ApiUncategorizedBudgetTransaction, categoryId: string) => {
    if (!categoryId) return;
    const categoryNameForId = activeCategories.find((category) => category.id === categoryId)?.name;
    if (!categoryNameForId) return;
    setPendingAssignment({ transaction, categoryId, treatmentName: categoryNameForId });
  };

  const completeAssignment = async (createRule: boolean) => {
    if (!pendingAssignment) return;
    setAssigning(true);
    setError(null);
    let transactionAssigned = false;
    try {
      if (pendingAssignment.transactionType) {
        await api.transactions.updateClassification(pendingAssignment.transaction.id, pendingAssignment.transactionType);
      } else if (pendingAssignment.categoryId) {
        await api.transactions.updateBudgetCategory(pendingAssignment.transaction.id, pendingAssignment.categoryId);
      }
      transactionAssigned = true;
      if (createRule) {
        await api.budgets.createMerchantRule({
          ...(pendingAssignment.categoryId ? { budget_category_id: pendingAssignment.categoryId } : {}),
          ...(pendingAssignment.transactionType ? { transaction_type: pendingAssignment.transactionType } : {}),
          merchant_pattern: pendingAssignment.transaction.merchant,
        });
      }
      setPendingAssignment(null);
      await reload();
      refreshData();
    } catch (err) {
      setPendingAssignment(null);
      setError(transactionAssigned
        ? (err instanceof ApiError ? `Transaction assigned, but the merchant rule wasn't saved: ${err.message}` : "Transaction assigned, but the merchant rule wasn't saved.")
        : (err instanceof ApiError ? err.message : "Couldn't assign that transaction."));
      await reload();
      if (transactionAssigned) refreshData();
    } finally {
      setAssigning(false);
    }
  };

  const approveTransaction = async (transactionId: string) => {
    setError(null);
    try {
      await api.transactions.markReviewed(transactionId);
      setUncategorized((rows) => rows.filter((row) => row.id !== transactionId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't approve that transaction.");
    }
  };

  const applySpecialTreatment = async (transactionId: string, type: "transfer" | "income" | "credit_card_payment") => {
    const transaction = uncategorized.find((row) => row.id === transactionId);
    if (!transaction) return;
    setPendingAssignment({
      transaction,
      transactionType: type,
      treatmentName: type === "income" ? "Income" : type === "credit_card_payment" ? "Credit card payment" : "Transfer",
    });
  };

  const viewCategoryTransactions = (categoryId: string) => {
    const [year, monthNumber] = month.split("-").map(Number);
    const lastDay = new Date(year, monthNumber, 0).getDate();
    const params = new URLSearchParams({
      budget_category_id: categoryId,
      since: `${month}-01`,
      until: `${month}-${String(lastDay).padStart(2, "0")}`,
    });
    router.push(`/transactions?${params.toString()}`);
  };

  return (
    <PageContainer>
      <PageHeader
        title="Budget"
        description="Assign every expense to a budget category, then track your month as it unfolds."
        actions={
          <div className="flex items-center rounded-md border border-border bg-card p-0.5">
            <Button variant="ghost" size="sm" className="h-7 w-7 px-0" onClick={() => setMonth((value) => shiftMonth(value, -1))} aria-label="Previous month"><ChevronLeft /></Button>
            <span className="min-w-28 px-2 text-center text-[12px] font-medium text-foreground">{formatMonth(month)}</span>
            <Button variant="ghost" size="sm" className="h-7 w-7 px-0" onClick={() => setMonth((value) => shiftMonth(value, 1))} aria-label="Next month"><ChevronRight /></Button>
          </div>
        }
      />

      {error && <p className="mb-4 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive" role="alert">{error}</p>}
      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[{ label: "Budgeted", amount: totalBudgeted }, { label: "Spent including pending", amount: allSpent }, { label: allSpent > totalBudgeted ? "Over budget" : "Remaining", amount: Math.abs(totalBudgeted - allSpent) }, { label: "Uncategorized spending", amount: unassignedSpent }].map((item) => <div key={item.label} className="rounded-lg border border-border bg-card p-4"><p className="text-xs text-muted-foreground">{item.label}</p><p className="mt-1 text-xl font-semibold tabular-nums">{loading ? "—" : formatCurrency(item.amount)}</p></div>)}
      </div>

      {summary?.reconciliation && <details className="mb-4 rounded-lg border border-border bg-card p-3 text-xs">
        <summary className="cursor-pointer font-medium">How budget spending relates to cash flow</summary>
        <div className="mt-3 grid gap-2 sm:grid-cols-4">
          <p>Cash-flow expenses, net of refunds<br /><strong>{formatCurrency(Number(summary.reconciliation.cash_flow_expenses))}</strong></p>
          <p>Less expenses excluded from budget<br /><strong>{formatCurrency(Number(summary.reconciliation.excluded_expenses))}</strong></p>
          <p>Less assigned reimbursements<br /><strong>{formatCurrency(Number(summary.reconciliation.reimbursements))}</strong></p>
          <p>Plus categorized outgoing transfers<br /><strong>{formatCurrency(Number(summary.reconciliation.categorized_transfer_spending ?? 0))}</strong></p>
          <p>Total budget spending<br /><strong>{formatCurrency(Number(summary.reconciliation.budget_spending))}</strong></p>
        </div>
        <p className="mt-3 text-muted-foreground">Includes pending transactions and uncategorized expenses for {formatMonth(month)}. Categorized outgoing transfers count as spending; categorized incoming transfers reimburse it. Unassigned transfers, income, and credit-card payments are excluded. Leave transfers between your own accounts uncategorized.</p>
      </details>}

      <div className="mb-4 grid gap-4 xl:grid-cols-2">
      <SpendingPaceChart summary={summary} month={month} budget={totalBudgeted} loading={loading} />
      <BudgetBreakdown summary={summary} loading={loading} onSelect={viewCategoryTransactions} />

      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2">
          <PanelHeader title="Monthly plan" description={loading ? "Loading your budget…" : `${formatCurrency(totalSpent)} categorized · ${formatMonth(month)}`} actions={<select aria-label="Category order" value={categoryOrder} onChange={(event) => setCategoryOrder(event.target.value)} className="h-8 rounded-md border border-border bg-background px-2 text-xs"><option value="over">Over budget first</option><option value="existing">Existing order</option><option value="group">Group by Needs / Wants / Other</option></select>} />
          {month === localMonthKey() && <p className="border-b border-border px-4 py-3 text-xs text-muted-foreground">Pace estimates extend spending so far across the full month. Fixed bills and one-time purchases may make this estimate too high; it is not a prediction of upcoming charges.</p>}
          <div className="divide-y divide-border">
            {orderedCategories.map((item, index) => {
              const budgeted = Number(item.budgeted);
              const spent = Number(item.spent);
              const pending = Number(item.pending);
              const used = spent + pending;
              const remaining = Number(item.remaining);
              const ratio = budgeted > 0 ? Math.min(100, Math.max(0, used / budgeted * 100)) : used > 0 ? 100 : 0;
              const overBudget = remaining < 0;
              return <div key={item.budget_category_id} className="p-4">
                {categoryOrder === "group" && (index === 0 || orderedCategories[index - 1].group_name !== item.group_name) && <h3 className="mb-4 border-b border-border pb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{item.group_name}</h3>}
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <button type="button" onClick={() => viewCategoryTransactions(item.budget_category_id)} className="font-medium text-foreground hover:underline" aria-label={`View ${item.name} transactions`}>{item.name}</button>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">{item.group_name}{pending !== 0 ? ` · ${formatCurrency(pending)} pending` : ""}</p>
                  </div>
                  <div className="flex items-center gap-1"><label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">Budget
                    <input key={`${month}:${budgeted}`} type="number" min="0" step="0.01" defaultValue={budgeted.toFixed(2)} onBlur={(event) => { if (Number(event.target.value) !== budgeted) void updateLimit(item.budget_category_id, event.target.value); }} className="h-7 w-24 rounded border border-border bg-background px-1.5 text-right font-mono text-[12px] tabular-nums text-foreground outline-none focus:border-ring" aria-label={`Monthly budget for ${item.name}`} />
                  </label><Button type="button" variant="ghost" size="icon-xs" className="text-destructive" aria-label={`Delete ${item.name}`} onClick={() => { const category = categories.find((row) => row.id === item.budget_category_id); if (category) void deleteCategory(category); }}><Trash2 /></Button></div>
                </div>
                <div className="mt-3 flex items-baseline justify-between gap-3 text-[12px]">
                  <span className="font-mono font-medium tabular-nums text-foreground">{formatCurrency(used)} / {formatCurrency(budgeted)}</span>
                  <span className={overBudget ? "font-mono tabular-nums text-destructive" : "font-mono tabular-nums text-positive"}>{overBudget ? `${formatCurrency(Math.abs(remaining))} over` : `${formatCurrency(remaining)} left`}</span>
                </div>
                <div className="mt-2 h-3 overflow-hidden rounded-full bg-muted" aria-label={`${item.name}: ${formatCurrency(used)} of ${formatCurrency(budgeted)}`}>
                  <div className={overBudget ? "h-full bg-destructive" : "h-full bg-primary"} style={{ width: `${ratio}%` }} />
                </div>
                {month === localMonthKey() && <p className="mt-1.5 text-[11px] text-muted-foreground">If spending continues at this rate: {formatCurrency(Number(item.forecast))} by month end</p>}
              </div>;
            })}
          </div>
          {!loading && summary?.categories.length === 0 && <p className="p-5 text-sm text-muted-foreground">Start with a few categories such as Groceries, Housing, and Dining.</p>}
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel>
            <PanelHeader title="Review progress" description="Review new activity and confirm how each transaction should be treated." />
            <div className="p-4">
              <p className="font-mono text-2xl font-semibold text-foreground">{loading ? "—" : uncategorized.length}</p>
              <p className="mt-1 text-[12px] text-muted-foreground">transactions awaiting review across all time</p>
              <p className="mt-3 text-[12px] text-muted-foreground">{formatCurrency(queuePosted)} posted · {formatCurrency(queuePending)} pending</p>
              <p className="mt-1 text-[11px] text-muted-foreground">Total transaction amounts awaiting review, across all time. Includes money in and out.</p>
              <a href="#transaction-review" className="mt-3 inline-block rounded text-xs font-medium text-primary underline underline-offset-4">Review {uncategorized.length} transaction{uncategorized.length === 1 ? "" : "s"}</a>
            </div>
          </Panel>
          <details className="rounded-lg border border-border bg-card">
            <summary className="cursor-pointer p-4 text-sm font-medium">Add category</summary>
            <form onSubmit={createCategory} className="flex flex-col gap-2 p-4">
              <label className="text-[11px] font-medium text-muted-foreground">Category name<input required value={categoryName} onChange={(event) => setCategoryName(event.target.value)} placeholder="e.g. Pet care" className="mt-1 h-8 w-full rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring" /></label>
              <div className="grid grid-cols-2 gap-2"><label className="text-[11px] font-medium text-muted-foreground">Group<select value={groupName} onChange={(event) => setGroupName(event.target.value)} className="mt-1 h-8 w-full rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring"><option>Needs</option><option>Wants</option><option>Other</option></select></label><label className="text-[11px] font-medium text-muted-foreground">Monthly budget<input required type="number" min="0" step="0.01" inputMode="decimal" value={limit} onChange={(event) => setLimit(event.target.value)} placeholder="0.00" className="mt-1 h-8 w-full rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring" /></label></div>
              <Button size="sm" type="submit"><Plus /> Add category</Button>
            </form>
          </details>
        </div>
      </div>

      <Panel id="transaction-review" className="mt-4 scroll-mt-4">
        <PanelHeader title="Transactions to review" description="Confirm each new transaction, change its category, or create a rule for matching activity. Incoming payments and transfers appear here too." />
        {uncategorized.length ? <div className="overflow-x-auto"><table className="w-full border-collapse text-[13px]"><thead><tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground"><th className="px-4 py-2">Merchant</th><th className="px-4 py-2">Provider category</th><th className="px-4 py-2">Your category</th><th className="px-4 py-2 text-right">Amount</th><th className="px-4 py-2 text-right">Action</th></tr></thead><tbody>{uncategorized.map((transaction) => <tr key={transaction.id} className="border-b border-border/60 last:border-0"><td className="px-4 py-3"><p className="font-medium text-foreground">{transaction.merchant}</p><p className="text-[11px] text-muted-foreground">{transaction.posted_at} · {transaction.type}{transaction.status === "pending" ? " · pending" : ""}</p></td><td className="px-4 py-3 text-muted-foreground">{transaction.provider_category}</td><td className="px-4 py-3"><select value={pendingAssignment?.transaction.id === transaction.id ? pendingAssignment.categoryId ?? (pendingAssignment.transactionType ? `__${pendingAssignment.transactionType}__` : "") : transaction.budget_category_id ?? (transaction.type === "income" ? "__income__" : transaction.type === "transfer" ? "__transfer__" : transaction.type === "credit_card_payment" ? "__credit_card_payment__" : "")} onChange={(event) => event.target.value === "__credit_card_payment__" ? void applySpecialTreatment(transaction.id, "credit_card_payment") : event.target.value === "__transfer__" ? void applySpecialTreatment(transaction.id, "transfer") : event.target.value === "__income__" ? void applySpecialTreatment(transaction.id, "income") : requestAssignment(transaction, event.target.value)} className="h-8 min-w-36 rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring"><option value="">Choose your category</option><option value="__transfer__">Transfer — exclude from cash flow</option><option value="__income__">Income — exclude from budget</option><option value="__credit_card_payment__">Credit card payment — exclude from budget and cash flow</option>{activeCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></td><td className={`px-4 py-3 text-right font-mono tabular-nums ${Number(transaction.amount) > 0 ? "text-positive" : ""}`}>{formatCurrency(Number(transaction.amount), { sign: true })}</td><td className="px-4 py-3 text-right"><Button type="button" variant="outline" size="sm" onClick={() => void approveTransaction(transaction.id)}><Check /> Approve</Button></td></tr>)}</tbody></table></div> : <div className="flex items-center gap-2 p-5 text-sm text-positive"><Tag className="size-4" />You're all caught up. Every transaction has been reviewed.</div>}
      </Panel>

      {pendingAssignment && <DialogShell onClose={() => setPendingAssignment(null)} closeDisabled={assigning} ariaLabelledBy="merchant-rule-title" panelClassName="max-w-md">
          <div className="border-b border-border px-4 py-3"><h2 id="merchant-rule-title" className="text-sm font-semibold text-foreground">Create a merchant rule?</h2><p className="mt-1 text-xs text-muted-foreground">Also classify and automatically approve past and future transactions from {pendingAssignment.transaction.merchant} as {pendingAssignment.treatmentName}.</p></div>
          <div className="flex justify-end gap-2 p-3"><Button type="button" variant="outline" size="sm" onClick={() => completeAssignment(false)} disabled={assigning}>Only this transaction</Button><Button type="button" size="sm" onClick={() => completeAssignment(true)} disabled={assigning}>{assigning ? "Saving…" : "Create rule"}</Button></div>
      </DialogShell>}
    </PageContainer>
  );
}
