"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Plus, Tag } from "lucide-react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { PageContainer, PageHeader } from "@/components/page-container";
import { Panel, PanelHeader } from "@/components/panel";
import { Button } from "@/components/ui/button";
import {
  api,
  ApiError,
  type ApiBudgetCategory,
  type ApiBudgetSummary,
  type ApiUncategorizedBudgetTransaction,
} from "@/lib/api-client";
import { formatCurrency } from "@/lib/data";

const currentMonth = new Date().toISOString().slice(0, 7);
const CHART_COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];

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
  categoryId: string;
  categoryName: string;
};

export default function BudgetPage() {
  const [month, setMonth] = useState(currentMonth);
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

  const activeCategories = useMemo(() => categories.filter((category) => category.active), [categories]);
  const chartData = useMemo(
    () => (summary?.categories ?? []).map((item, index) => ({
      name: item.name,
      budgeted: Number(item.budgeted),
      spent: Number(item.spent),
      color: CHART_COLORS[index % CHART_COLORS.length],
    })),
    [summary],
  );
  const spendingChartData = chartData.filter((item) => item.spent > 0);
  const totalBudgeted = chartData.reduce((sum, item) => sum + item.budgeted, 0);
  const totalSpent = chartData.reduce((sum, item) => sum + item.spent, 0);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextSummary, nextCategories, nextUncategorized] = await Promise.all([
        api.budgets.summary(month),
        api.budgets.categories(),
        api.budgets.uncategorized(month),
      ]);
      setSummary(nextSummary);
      setCategories(nextCategories);
      setUncategorized(nextUncategorized);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load your budget.");
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => { void reload(); }, [reload]);

  const createCategory = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await api.budgets.createCategory({ name: categoryName, group_name: groupName, monthly_limit: limit || "0" });
      setCategoryName("");
      setLimit("");
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create the category.");
    }
  };

  const updateLimit = async (categoryId: string, monthlyLimit: string) => {
    if (!monthlyLimit || Number.isNaN(Number(monthlyLimit)) || Number(monthlyLimit) < 0) return;
    try {
      await api.budgets.updateCategory(categoryId, { monthly_limit: monthlyLimit });
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't update the monthly budget.");
    }
  };

  const requestAssignment = (transaction: ApiUncategorizedBudgetTransaction, categoryId: string) => {
    if (!categoryId) return;
    const categoryNameForId = activeCategories.find((category) => category.id === categoryId)?.name;
    if (!categoryNameForId) return;
    setPendingAssignment({ transaction, categoryId, categoryName: categoryNameForId });
  };

  const completeAssignment = async (createRule: boolean) => {
    if (!pendingAssignment) return;
    setAssigning(true);
    setError(null);
    let transactionAssigned = false;
    try {
      await api.transactions.updateBudgetCategory(pendingAssignment.transaction.id, pendingAssignment.categoryId);
      transactionAssigned = true;
      if (createRule) {
        await api.budgets.createMerchantRule({
          budget_category_id: pendingAssignment.categoryId,
          merchant_pattern: pendingAssignment.transaction.merchant,
        });
      }
      setPendingAssignment(null);
      await reload();
    } catch (err) {
      setPendingAssignment(null);
      setError(transactionAssigned
        ? (err instanceof ApiError ? `Transaction assigned, but the merchant rule wasn't saved: ${err.message}` : "Transaction assigned, but the merchant rule wasn't saved.")
        : (err instanceof ApiError ? err.message : "Couldn't assign that transaction."));
      await reload();
    } finally {
      setAssigning(false);
    }
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

      <Panel className="mb-4">
        <PanelHeader title="This month’s spending" description="Posted categorized expenses, grouped by where they were assigned — not by your budget allocation." />
        <div className="flex min-h-64 flex-col gap-4 p-4 sm:flex-row sm:items-center">{spendingChartData.length ? <><div className="h-56 min-w-0 flex-1"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={spendingChartData} dataKey="spent" nameKey="name" innerRadius="58%" outerRadius="82%" paddingAngle={2}>{spendingChartData.map((item) => <Cell key={item.name} fill={item.color} />)}</Pie><Tooltip formatter={(value) => formatCurrency(Number(value))} /></PieChart></ResponsiveContainer></div><div className="w-full space-y-2 text-[12px] sm:max-w-72">{spendingChartData.map((item) => <p key={item.name} className="flex items-center gap-2 text-muted-foreground"><span className="size-2.5 shrink-0 rounded-sm" style={{ background: item.color }} /><span className="min-w-0 flex-1 truncate">{item.name}</span><span className="font-mono tabular-nums text-foreground">{formatCurrency(item.spent)}</span></p>)}</div></> : <p className="flex min-h-56 w-full items-center justify-center text-center text-sm text-muted-foreground">Categorize this month’s expenses to see how your spending is distributed.</p>}</div>
      </Panel>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2">
          <PanelHeader title="Monthly plan" description={loading ? "Loading your budget…" : `${formatCurrency(totalSpent)} spent of ${formatCurrency(totalBudgeted)} budgeted`} />
          <div className="divide-y divide-border">
            {summary?.categories.map((item) => {
              const budgeted = Number(item.budgeted);
              const spent = Number(item.spent);
              const remaining = Number(item.remaining);
              const ratio = budgeted > 0 ? Math.min(100, Math.max(0, spent / budgeted * 100)) : spent > 0 ? 100 : 0;
              const overBudget = remaining < 0;
              return <div key={item.budget_category_id} className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-foreground">{item.name}</p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">{item.group_name}{Number(item.pending) > 0 ? ` · ${formatCurrency(Number(item.pending))} pending` : ""}</p>
                  </div>
                  <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">Budget
                    <input type="number" min="0" step="1" defaultValue={budgeted} onBlur={(event) => updateLimit(item.budget_category_id, event.target.value)} className="h-7 w-24 rounded border border-border bg-background px-1.5 text-right font-mono text-[12px] tabular-nums text-foreground outline-none focus:border-ring" aria-label={`Monthly budget for ${item.name}`} />
                  </label>
                </div>
                <div className="mt-3 flex items-baseline justify-between gap-3 text-[12px]">
                  <span className="font-mono font-medium tabular-nums text-foreground">{formatCurrency(spent)} / {formatCurrency(budgeted)}</span>
                  <span className={overBudget ? "font-mono tabular-nums text-destructive" : "font-mono tabular-nums text-positive"}>{overBudget ? `${formatCurrency(Math.abs(remaining))} over` : `${formatCurrency(remaining)} left`}</span>
                </div>
                <div className="mt-2 h-3 overflow-hidden rounded-full bg-muted" aria-label={`${item.name}: ${formatCurrency(spent)} of ${formatCurrency(budgeted)}`}>
                  <div className={overBudget ? "h-full bg-destructive" : "h-full bg-primary"} style={{ width: `${ratio}%` }} />
                </div>
                <p className="mt-1.5 text-[11px] text-muted-foreground">At this pace: {formatCurrency(Number(item.forecast))} this month</p>
              </div>;
            })}
          </div>
          {!loading && summary?.categories.length === 0 && <p className="p-5 text-sm text-muted-foreground">Start with a few categories such as Groceries, Housing, and Dining.</p>}
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel>
            <PanelHeader title="Categorization progress" description="Every assigned expense becomes part of your budget." />
            <div className="p-4">
              <p className="font-mono text-2xl font-semibold text-foreground">{uncategorized.length}</p>
              <p className="mt-1 text-[12px] text-muted-foreground">uncategorized transactions this month</p>
              <p className="mt-3 text-[12px] text-muted-foreground">{formatCurrency(Number(summary?.uncategorized.spent ?? 0))} posted · {formatCurrency(Number(summary?.uncategorized.pending ?? 0))} pending</p>
            </div>
          </Panel>
          <Panel>
            <PanelHeader title="Add a custom category" description="A category is where spending counts. A group only organizes categories as Needs, Wants, or Other." />
            <form onSubmit={createCategory} className="flex flex-col gap-2 p-4">
              <label className="text-[11px] font-medium text-muted-foreground">Category name<input required value={categoryName} onChange={(event) => setCategoryName(event.target.value)} placeholder="e.g. Pet care" className="mt-1 h-8 w-full rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring" /></label>
              <div className="grid grid-cols-2 gap-2"><label className="text-[11px] font-medium text-muted-foreground">Group<select value={groupName} onChange={(event) => setGroupName(event.target.value)} className="mt-1 h-8 w-full rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring"><option>Needs</option><option>Wants</option><option>Other</option></select></label><label className="text-[11px] font-medium text-muted-foreground">Monthly budget<input required inputMode="decimal" value={limit} onChange={(event) => setLimit(event.target.value)} placeholder="$0" className="mt-1 h-8 w-full rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring" /></label></div>
              <Button size="sm" type="submit"><Plus /> Add category</Button>
            </form>
          </Panel>
        </div>
      </div>

      <Panel className="mt-4">
        <PanelHeader title="Uncategorized inbox" description="Choose a category for each expense. We’ll then ask whether that merchant should become a rule." />
        {uncategorized.length ? <div className="overflow-x-auto"><table className="w-full border-collapse text-[13px]"><thead><tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground"><th className="px-4 py-2">Merchant</th><th className="px-4 py-2">Provider category</th><th className="px-4 py-2">Assign to</th><th className="px-4 py-2 text-right">Amount</th></tr></thead><tbody>{uncategorized.map((transaction) => <tr key={transaction.id} className="border-b border-border/60 last:border-0"><td className="px-4 py-3"><p className="font-medium text-foreground">{transaction.merchant}</p><p className="text-[11px] text-muted-foreground">{transaction.posted_at}{transaction.status === "pending" ? " · pending" : ""}</p></td><td className="px-4 py-3 text-muted-foreground">{transaction.provider_category}</td><td className="px-4 py-3"><select value={pendingAssignment?.transaction.id === transaction.id ? pendingAssignment.categoryId : ""} onChange={(event) => requestAssignment(transaction, event.target.value)} className="h-8 min-w-36 rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring"><option value="" disabled>Choose category</option>{activeCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></td><td className="px-4 py-3 text-right font-mono tabular-nums">{formatCurrency(Math.abs(Number(transaction.amount)))}</td></tr>)}</tbody></table></div> : <div className="flex items-center gap-2 p-5 text-sm text-positive"><Tag className="size-4" />Everything in this month is categorized.</div>}
      </Panel>

      {pendingAssignment && <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/20 p-4 backdrop-blur-sm" onMouseDown={() => !assigning && setPendingAssignment(null)}>
        <div role="dialog" aria-modal="true" aria-labelledby="merchant-rule-title" className="w-full max-w-md rounded-xl border border-border bg-popover shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
          <div className="border-b border-border px-4 py-3"><h2 id="merchant-rule-title" className="text-sm font-semibold text-foreground">Create a merchant rule?</h2><p className="mt-1 text-xs text-muted-foreground">Also categorize past and future unassigned expenses from {pendingAssignment.transaction.merchant} as {pendingAssignment.categoryName}.</p></div>
          <div className="flex justify-end gap-2 p-3"><Button type="button" variant="outline" size="sm" onClick={() => completeAssignment(false)} disabled={assigning}>Only this transaction</Button><Button type="button" size="sm" onClick={() => completeAssignment(true)} disabled={assigning}>{assigning ? "Saving…" : "Create rule"}</Button></div>
        </div>
      </div>}
    </PageContainer>
  );
}
