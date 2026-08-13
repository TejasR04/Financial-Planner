"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Plus, RotateCcw } from "lucide-react";
import { TransactionEntryDialog } from "@/components/transaction-entry-dialog";
import { TransactionEditDialog } from "@/components/transaction-edit-dialog";
import { PageContainer, PageHeader } from "@/components/page-container";
import { Panel, PanelHeader } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { DialogShell } from "@/components/ui/dialog-shell";
import { ApiError, api, type ApiBudgetCategory, type ApiTransaction, type ApiTransactionList } from "@/lib/api-client";
import { formatCurrency } from "@/lib/data";
import { useAccountsData, useDataRefresh } from "@/lib/data-provider";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 50;

type PendingMerchantRule = {
  transaction: ApiTransaction;
  categoryId?: string;
  transactionType?: "income" | "transfer" | "credit_card_payment";
  treatmentName: string;
};

function formatDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function TransactionsPage() {
  const accounts = useAccountsData();
  const refreshData = useDataRefresh();
  const [accountId, setAccountId] = useState("");
  const [merchant, setMerchant] = useState("");
  const [budgetCategoryId, setBudgetCategoryId] = useState("");
  const [direction, setDirection] = useState<"" | "inflow" | "outflow">("");
  const [categories, setCategories] = useState<ApiBudgetCategory[]>([]);
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [cashFlowOnly, setCashFlowOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [result, setResult] = useState<ApiTransactionList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [entryOpen, setEntryOpen] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);
  const [editing, setEditing] = useState<ApiTransaction | null>(null);
  const [updatingCategoryId, setUpdatingCategoryId] = useState<string | null>(null);
  const [filtersReady, setFiltersReady] = useState(false);
  const [pendingMerchantRule, setPendingMerchantRule] = useState<PendingMerchantRule | null>(null);

  const accountNameById = useMemo(
    () => new Map(accounts.map((account) => [account.id, account.name])),
    [accounts],
  );

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setBudgetCategoryId(params.get("budget_category_id") ?? "");
    setSince(params.get("since") ?? "");
    setUntil(params.get("until") ?? "");
    setDirection((params.get("direction") as "inflow" | "outflow" | null) ?? "");
    setCashFlowOnly(params.get("cash_flow_only") === "true");
    setFiltersReady(true);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void api.budgets.categories(controller.signal).then(setCategories).catch(() => {
      if (!controller.signal.aborted) setCategories([]);
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!filtersReady) return;
    let cancelled = false;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    const handle = window.setTimeout(() => {
      api.transactions
        .list({
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
          accountId: accountId || undefined,
          budgetCategoryId: budgetCategoryId || undefined,
          direction: direction || undefined,
          search: merchant.trim() || undefined,
          since: since || undefined,
          until: until || undefined,
          includeArchived,
          cashFlowOnly,
        }, controller.signal)
        .then((next) => {
          if (!cancelled) setResult(next);
        })
        .catch((err) => {
          if (!cancelled && !controller.signal.aborted) {
            setError(err instanceof ApiError ? err.message : "Couldn't load transactions.");
            setResult(null);
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, merchant ? 300 : 0);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
      controller.abort();
    };
  }, [accountId, budgetCategoryId, cashFlowOnly, direction, filtersReady, includeArchived, merchant, page, reloadTick, since, until]);

  const resetFilters = () => {
    setAccountId("");
    setMerchant("");
    setBudgetCategoryId("");
    setDirection("");
    setSince("");
    setUntil("");
    setIncludeArchived(false);
    setCashFlowOnly(false);
    setPage(0);
  };
  const updateCategory = async (transaction: ApiTransaction, nextCategoryId: string) => {
    if (["__transfer__", "__income__", "__credit_card_payment__"].includes(nextCategoryId)) {
      const transactionType = nextCategoryId.slice(2, -2) as "transfer" | "income" | "credit_card_payment";
      setPendingMerchantRule({
        transaction,
        transactionType,
        treatmentName: transactionType === "income" ? "Income" : transactionType === "transfer" ? "Transfer" : "Credit card payment",
      });
      return;
    }
    if (nextCategoryId) {
      const categoryName = categories.find((category) => category.id === nextCategoryId)?.name;
      if (categoryName) {
        setPendingMerchantRule({ transaction, categoryId: nextCategoryId, treatmentName: categoryName });
        return;
      }
    }
    setUpdatingCategoryId(transaction.id);
    setError(null);
    try {
      await api.transactions.updateBudgetCategory(transaction.id, nextCategoryId || null, false);
      setReloadTick((current) => current + 1);
      refreshData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't update that category.");
    } finally {
      setUpdatingCategoryId(null);
    }
  };
  const completeCategoryAssignment = async (createRule: boolean) => {
    if (!pendingMerchantRule) return;
    const pending = pendingMerchantRule;
    setUpdatingCategoryId(pending.transaction.id);
    setError(null);
    try {
      if (pending.transactionType) {
        await api.transactions.updateClassification(pending.transaction.id, pending.transactionType);
      } else if (pending.categoryId) {
        await api.transactions.updateBudgetCategory(pending.transaction.id, pending.categoryId, false);
      }
      if (createRule) {
        await api.budgets.createMerchantRule({
          ...(pending.categoryId ? { budget_category_id: pending.categoryId } : {}),
          ...(pending.transactionType ? { transaction_type: pending.transactionType } : {}),
          merchant_pattern: pending.transaction.merchant,
        });
      }
      setPendingMerchantRule(null);
      setReloadTick((current) => current + 1);
      refreshData();
    } catch (err) {
      setPendingMerchantRule(null);
      setError(err instanceof ApiError ? err.message : "Couldn't update that category.");
      setReloadTick((current) => current + 1);
    } finally {
      setUpdatingCategoryId(null);
    }
  };
  const setFilterPage = (update: () => void) => {
    update();
    setPage(0);
  };
  const total = result?.total ?? 0;
  const first = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const last = Math.min((page + 1) * PAGE_SIZE, total);

  return (
    <PageContainer>
      <PageHeader
        title="Transactions"
        description="Search and review activity across every connected account"
        actions={<Button size="sm" onClick={() => setEntryOpen(true)}><Plus /> Add transactions</Button>}
      />
      {editing && <TransactionEditDialog transaction={editing} account={accounts.find((a) => a.id === editing.account_id)} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); setReloadTick((x) => x + 1); refreshData(); }} />}

      <Panel>
        <PanelHeader title="Filters" description="Search by merchant or amount, or narrow the ledger by account, budget category, or date" />
        <div className="grid grid-cols-1 gap-3 border-t border-border p-4 sm:grid-cols-2 xl:grid-cols-8">
          <input
            value={merchant}
            onChange={(event) => setFilterPage(() => setMerchant(event.target.value))}
            placeholder="Search merchant or amount"
            className="h-8 rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none placeholder:text-muted-foreground focus:border-ring"
            aria-label="Search transactions by merchant or amount"
          />
          <select
            value={accountId}
            onChange={(event) => setFilterPage(() => setAccountId(event.target.value))}
            className="h-8 rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring"
            aria-label="Filter by account"
          >
            <option value="">All accounts</option>
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>{account.name}</option>
            ))}
          </select>
          <select
            value={budgetCategoryId}
            onChange={(event) => setFilterPage(() => setBudgetCategoryId(event.target.value))}
            className="h-8 rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring"
            aria-label="Filter by category"
          >
            <option value="">All budget categories</option>
            {categories.filter((category) => category.active).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
          <select value={direction} onChange={(event) => setFilterPage(() => setDirection(event.target.value as "" | "inflow" | "outflow"))} className="h-8 rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring" aria-label="Filter by money direction"><option value="">Money in and out</option><option value="inflow">Money in (positive)</option><option value="outflow">Money out (negative)</option></select>
          <label className="flex items-center gap-2 text-[12px] text-muted-foreground">
            From
            <input type="date" value={since} onChange={(event) => setFilterPage(() => setSince(event.target.value))} className="h-8 min-w-0 flex-1 rounded-md border border-border bg-background px-2 text-foreground outline-none focus:border-ring" />
          </label>
          <label className="flex items-center gap-2 text-[12px] text-muted-foreground"><input type="checkbox" checked={includeArchived} onChange={(event) => setFilterPage(() => setIncludeArchived(event.target.checked))} />Include disconnected accounts</label>
          <label className="flex items-center gap-2 text-[12px] text-muted-foreground">
            To
            <input type="date" value={until} onChange={(event) => setFilterPage(() => setUntil(event.target.value))} className="h-8 min-w-0 flex-1 rounded-md border border-border bg-background px-2 text-foreground outline-none focus:border-ring" />
          </label>
          <Button variant="outline" size="sm" onClick={resetFilters} disabled={!accountId && !merchant && !budgetCategoryId && !direction && !since && !until && !includeArchived}>
            <RotateCcw /> Reset filters
          </Button>
        </div>
      </Panel>

      <Panel className="mt-4">
        <PanelHeader
          title="All activity"
          description={loading ? "Loading transactions…" : total ? `Showing ${first}–${last} of ${total}` : "No transactions match these filters"}
        />
        {error ? (
          <p role="alert" className="p-4 text-sm text-destructive">{error}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-2 font-medium">Date</th>
                  <th className="px-4 py-2 font-medium">Merchant</th>
                  <th className="px-4 py-2 font-medium">Category</th>
                  <th className="hidden px-4 py-2 font-medium md:table-cell">Account</th>
                  <th className="hidden px-4 py-2 font-medium lg:table-cell">Type</th>
                  <th className="px-4 py-2 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                {result?.data.map((transaction) => (
                  <tr key={transaction.id} className="border-b border-border/60 transition-colors last:border-0 hover:bg-muted/40">
                    <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-muted-foreground tabular-nums">{formatDate(transaction.posted_at)}</td>
                    <td className="px-4 py-2.5 font-medium text-foreground">
                      <button className="text-left hover:underline" onClick={() => setEditing(transaction)}>{transaction.merchant}</button>
                      {transaction.status === "pending" && <span className="ml-2 rounded border border-warning/30 bg-warning/10 px-1 py-px text-[10px] font-medium text-warning">pending</span>}
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      <select
                        value={transaction.budget_category_id ?? (transaction.type === "income" ? "__income__" : transaction.type === "transfer" ? "__transfer__" : transaction.type === "credit_card_payment" ? "__credit_card_payment__" : "")}
                        onChange={(event) => void updateCategory(transaction, event.target.value)}
                        disabled={updatingCategoryId === transaction.id}
                        aria-label={`Category for ${transaction.merchant}`}
                        className="h-8 min-w-40 rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none focus:border-ring disabled:opacity-60"
                      >
                        <option value="">{transaction.category}</option>
                        <option value="__transfer__">Transfer — exclude from cash flow</option>
                        <option value="__income__">Income — exclude from budget</option>
                        <option value="__credit_card_payment__">Credit card payment — exclude from budget and cash flow</option>
                        {categories.filter((category) => category.active).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                      </select>
                      <label className="mt-1 flex items-center gap-1 text-[11px]"><input type="checkbox" checked={transaction.ignored_from_budget} disabled={updatingCategoryId === transaction.id} onChange={(event) => { setUpdatingCategoryId(transaction.id); void api.transactions.updateBudgetCategory(transaction.id, transaction.budget_category_id, event.target.checked).then(() => { setReloadTick((current) => current + 1); refreshData(); }).catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't update budget handling.")).finally(() => setUpdatingCategoryId(null)); }} />Ignore for budget</label>
                    </td>
                    <td className="hidden px-4 py-2.5 text-muted-foreground md:table-cell">{transaction.account_name ?? accountNameById.get(transaction.account_id) ?? "Account"}{transaction.account_archived ? " (disconnected)" : ""}</td>
                    <td className="hidden px-4 py-2.5 capitalize text-muted-foreground lg:table-cell">{transaction.type}</td>
                    <td className={cn("whitespace-nowrap px-4 py-2.5 text-right font-mono font-medium tabular-nums", Number(transaction.amount) >= 0 ? "text-positive" : "text-foreground")}>
                      {formatCurrency(Number(transaction.amount), { sign: true })}
                    </td>
                  </tr>
                ))}
                {!loading && result?.data.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-10 text-center text-sm text-muted-foreground">No matching transactions.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-end gap-2 border-t border-border p-3">
            <Button variant="outline" size="sm" onClick={() => setPage((current) => current - 1)} disabled={page === 0 || loading}><ChevronLeft /> Previous</Button>
            <Button variant="outline" size="sm" onClick={() => setPage((current) => current + 1)} disabled={loading || last >= total}>Next <ChevronRight /></Button>
          </div>
        )}
      </Panel>
      {notice && <p className="mt-4 rounded-md border border-positive/30 bg-positive/5 px-3 py-2 text-sm text-positive" role="status">{notice}</p>}
      <TransactionEntryDialog
        open={entryOpen}
        accounts={accounts}
        onClose={() => setEntryOpen(false)}
        onSaved={(message) => {
          setEntryOpen(false);
          setNotice(message);
          setReloadTick((current) => current + 1);
          refreshData();
        }}
      />
      {pendingMerchantRule && <DialogShell onClose={() => setPendingMerchantRule(null)} closeDisabled={updatingCategoryId === pendingMerchantRule.transaction.id} ariaLabelledBy="transaction-merchant-rule-title" panelClassName="max-w-md">
        <div className="border-b border-border px-4 py-3"><h2 id="transaction-merchant-rule-title" className="text-sm font-semibold text-foreground">Create a merchant rule?</h2><p className="mt-1 text-xs text-muted-foreground">Also classify and automatically approve past and future transactions from {pendingMerchantRule.transaction.merchant} as {pendingMerchantRule.treatmentName}.</p></div>
        <div className="flex justify-end gap-2 p-3"><Button type="button" variant="outline" size="sm" onClick={() => void completeCategoryAssignment(false)} disabled={updatingCategoryId === pendingMerchantRule.transaction.id}>Only this transaction</Button><Button type="button" size="sm" onClick={() => void completeCategoryAssignment(true)} disabled={updatingCategoryId === pendingMerchantRule.transaction.id}>{updatingCategoryId === pendingMerchantRule.transaction.id ? "Saving…" : "Create rule"}</Button></div>
      </DialogShell>}
    </PageContainer>
  );
}
