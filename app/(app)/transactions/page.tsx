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
import { applyToTransactions } from "@/lib/bulk-transactions";

const PAGE_SIZE = 50;

function localDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function monthRange(date = new Date()) {
  return [localDate(new Date(date.getFullYear(), date.getMonth(), 1)), localDate(new Date(date.getFullYear(), date.getMonth() + 1, 0))];
}

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
  const [transactionType, setTransactionType] = useState<ApiTransaction["type"] | "">("");
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
  const [categoryEditingId, setCategoryEditingId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkCategory, setBulkCategory] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);

  const accountNameById = useMemo(
    () => new Map(accounts.map((account) => [account.id, account.name])),
    [accounts],
  );

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setBudgetCategoryId(params.get("budget_category_id") ?? "");
    const [start, end] = monthRange();
    const hasDates = params.has("since") || params.has("until");
    setSince(hasDates ? params.get("since") ?? "" : start);
    setUntil(hasDates ? params.get("until") ?? "" : end);
    setDirection((params.get("direction") as "inflow" | "outflow" | null) ?? "");
    setCashFlowOnly(params.get("cash_flow_only") === "true");
    const requestedType = params.get("type");
    if (["income", "expense", "transfer", "credit_card_payment", "contribution"].includes(requestedType ?? "")) setTransactionType(requestedType as ApiTransaction["type"]);
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
          type: transactionType || undefined,
          includeTotals: true,
        }, controller.signal)
        .then((next) => {
          if (cancelled) return;
          const lastValidPage = Math.max(0, Math.ceil(next.total / PAGE_SIZE) - 1);
          if (page > lastValidPage) {
            setPage(lastValidPage);
            return;
          }
          setResult(next);
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
  }, [accountId, budgetCategoryId, cashFlowOnly, direction, filtersReady, includeArchived, merchant, page, reloadTick, since, until, transactionType]);

  useEffect(() => {
    setSelectedIds([]);
    setCategoryEditingId(null);
  }, [accountId, budgetCategoryId, cashFlowOnly, direction, includeArchived, merchant, page, since, until, transactionType]);

  const applyBulk = async (action: "approve" | "category") => {
    if (!selectedIds.length || bulkBusy || loading || (action === "category" && !bulkCategory)) return;
    setBulkBusy(true);
    setNotice(null);
    const outcome = await applyToTransactions(selectedIds, (id) => action === "approve"
      ? api.transactions.markReviewed(id)
      : api.transactions.updateBudgetCategory(id, bulkCategory));
    setSelectedIds(outcome.failed);
    setNotice(`${outcome.succeeded.length} transaction${outcome.succeeded.length === 1 ? "" : "s"} ${action === "approve" ? "approved" : "categorized"}.${outcome.failed.length ? ` ${outcome.failed.length} failed and remain selected. ${outcome.errors[0]}` : ""}`);
    setReloadTick((current) => current + 1);
    refreshData();
    setBulkBusy(false);
  };

  const selectPeriod = (period: string) => {
    if (!period) return;
    const today = new Date();
    const start = period === "last" ? new Date(today.getFullYear(), today.getMonth() - 1, 1) : period === "year" ? new Date(today.getFullYear(), 0, 1) : new Date(today.getFullYear(), today.getMonth(), 1);
    const end = period === "last" ? new Date(today.getFullYear(), today.getMonth(), 0) : period === "this" ? new Date(today.getFullYear(), today.getMonth() + 1, 0) : today;
    setFilterPage(() => { setSince(period === "all" ? "" : localDate(start)); setUntil(period === "all" ? "" : localDate(end)); });
  };

  const resetFilters = () => {
    setAccountId("");
    setMerchant("");
    setBudgetCategoryId("");
    setDirection("");
    const [start, end] = monthRange();
    setSince(start);
    setUntil(end);
    setIncludeArchived(false);
    setCashFlowOnly(false);
    setTransactionType("");
    setPage(0);
  };
  const updateCategory = async (transaction: ApiTransaction, nextCategoryId: string) => {
    setCategoryEditingId(null);
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
      await api.transactions.updateBudgetCategory(transaction.id, nextCategoryId || null);
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
        await api.transactions.updateBudgetCategory(pending.transaction.id, pending.categoryId);
      }
      if (createRule) {
        try { await api.budgets.createMerchantRule({
          ...(pending.categoryId ? { budget_category_id: pending.categoryId } : {}),
          ...(pending.transactionType ? { transaction_type: pending.transactionType } : {}),
          merchant_pattern: pending.transaction.merchant,
        }); } catch (ruleError) {
          setNotice("Transaction updated, but the merchant rule could not be created.");
          setError(ruleError instanceof ApiError ? ruleError.message : "Couldn't create that merchant rule.");
        }
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
  const selectedDate = since ? new Date(`${since}T00:00:00`) : new Date();
  const [monthStart, monthEnd] = monthRange(selectedDate);
  const isFullMonth = since === monthStart && until === monthEnd;
  const periodLabel = isFullMonth
    ? selectedDate.toLocaleDateString("en-US", { month: "long", year: "numeric" })
    : !since && !until ? "All dates" : `${since ? formatDate(since) : "Beginning"} – ${until ? formatDate(until) : "Present"}`;
  const changeMonth = (offset: number) => {
    const [start, end] = monthRange(new Date(selectedDate.getFullYear(), selectedDate.getMonth() + offset, 1));
    setFilterPage(() => { setSince(start); setUntil(end); });
  };

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
        <fieldset disabled={bulkBusy} className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 xl:grid-cols-4">
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
          <label className="flex items-center gap-2 text-[12px] text-muted-foreground">
            To
            <input type="date" value={until} onChange={(event) => setFilterPage(() => setUntil(event.target.value))} className="h-8 min-w-0 flex-1 rounded-md border border-border bg-background px-2 text-foreground outline-none focus:border-ring" />
          </label>
          <select aria-label="Date preset" value="" onChange={(event) => selectPeriod(event.target.value)} className="h-8 rounded-md border border-border bg-background px-2 text-xs"><option value="">Choose a date period</option><option value="this">This month</option><option value="last">Last month</option><option value="year">Year to date</option><option value="all">All dates</option></select>
          <select aria-label="Filter by transaction type" value={transactionType} onChange={(event) => setFilterPage(() => setTransactionType(event.target.value as ApiTransaction["type"] | ""))} className="h-8 rounded-md border border-border bg-background px-2 text-xs"><option value="">All transaction types</option><option value="expense">Expenses and refunds</option><option value="income">Income</option><option value="transfer">Transfers</option><option value="credit_card_payment">Credit card payments</option><option value="contribution">Contributions</option></select>
          <label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={includeArchived} onChange={(event) => setFilterPage(() => setIncludeArchived(event.target.checked))} />Include disconnected accounts</label>
          <label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={cashFlowOnly} onChange={(event) => setFilterPage(() => setCashFlowOnly(event.target.checked))} />Cash-flow activity only</label>
          <Button variant="outline" size="sm" onClick={resetFilters} disabled={!accountId && !merchant && !budgetCategoryId && !direction && !since && !until && !includeArchived && !transactionType && !cashFlowOnly}>
            <RotateCcw /> Reset filters
          </Button>
        </fieldset>
      </Panel>

      <div className="mt-4 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold">{periodLabel}</h2>
        <div className="flex gap-2"><Button size="sm" variant="outline" aria-label="Previous month" onClick={() => changeMonth(-1)}><ChevronLeft /></Button><Button size="sm" variant="outline" aria-label="Next month" onClick={() => changeMonth(1)}><ChevronRight /></Button></div>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[{ label: "Income", value: result?.totals?.income }, { label: "Spending", value: result?.totals?.spending }, { label: "Net cash flow", value: result?.totals?.net_cash_flow }].map((item) => <div key={item.label} className="rounded-lg border border-border bg-card p-3"><p className="text-xs text-muted-foreground">{item.label}</p><p className="mt-1 text-lg font-semibold tabular-nums">{loading || item.value == null ? "—" : formatCurrency(Number(item.value), { sign: item.label === "Net cash flow" })}</p></div>)}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{periodLabel} · Totals follow the filters across all pages, including pending activity. Spending is net of refunds; transfers and card payments are excluded. Net cash flow is income minus spending, not your available account balance.</p>
      {notice && <p className="mt-3 rounded-md border border-border bg-muted/30 p-3 text-sm" role="status">{notice}</p>}

      <Panel className="mt-4">
        <PanelHeader
          title={`Activity · ${periodLabel}`}
          description={loading ? "Loading transactions…" : total ? `Showing ${first}–${last} of ${total}` : "No transactions match these filters"}
        />
        {selectedIds.length > 0 && <div className="flex flex-wrap items-center gap-3 border-b border-border bg-muted/30 p-3">
          <span className="text-xs font-medium">{selectedIds.length} selected on this page</span>
          <select aria-label="Bulk budget category" value={bulkCategory} disabled={bulkBusy || loading} onChange={(event) => setBulkCategory(event.target.value)} className="h-8 rounded-md border border-border bg-background px-2 text-xs"><option value="">Choose category</option>{categories.filter((category) => category.active).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select>
          <Button size="sm" variant="outline" disabled={!bulkCategory || bulkBusy || loading} onClick={() => void applyBulk("category")}>Apply category</Button>
          <Button size="sm" disabled={bulkBusy || loading} onClick={() => void applyBulk("approve")}>{bulkBusy ? "Saving…" : "Approve selected"}</Button>
          <Button size="sm" variant="ghost" disabled={bulkBusy} onClick={() => setSelectedIds([])}>Clear selection</Button>
          <p className="w-full text-xs text-muted-foreground">Categories apply to expenses and transfers. Categorized outgoing transfers add budget spending; incoming transfers reimburse it. Budget exclusions are preserved. No merchant rules are created.</p>
        </div>}
        {error ? (
          <p role="alert" className="p-4 text-sm text-destructive">{error}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  <th className="w-10 px-3 py-2"><input type="checkbox" aria-label="Select all transactions on this page" disabled={loading || bulkBusy || !result?.data.length} checked={!!result?.data.length && result.data.every((row) => selectedIds.includes(row.id))} onChange={(event) => setSelectedIds(event.target.checked ? (result?.data ?? []).map((row) => row.id) : [])} /></th>
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
                    <td className="px-3 py-2"><input type="checkbox" aria-label={`Select ${transaction.merchant} ${transaction.id}`} disabled={loading || bulkBusy} checked={selectedIds.includes(transaction.id)} onChange={(event) => setSelectedIds((ids) => event.target.checked ? [...ids, transaction.id] : ids.filter((id) => id !== transaction.id))} /></td>
                    <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-muted-foreground tabular-nums">{formatDate(transaction.posted_at)}</td>
                    <td className="px-4 py-2.5 font-medium text-foreground">
                      <button className="text-left hover:underline" disabled={bulkBusy || loading} onClick={() => setEditing(transaction)}>{transaction.merchant}</button>
                      {transaction.status === "pending" && <span className="ml-2 rounded border border-warning/30 bg-warning/10 px-1 py-px text-[10px] font-medium text-warning">pending</span>}
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {categoryEditingId === transaction.id ? <select
                        autoFocus
                        value={transaction.budget_category_id ?? ""}
                        onChange={(event) => void updateCategory(transaction, event.target.value)}
                        onBlur={() => setCategoryEditingId(null)}
                        disabled={updatingCategoryId === transaction.id}
                        aria-label={`Category for ${transaction.merchant}`}
                        className="h-8 rounded-md border border-border bg-background px-2 text-xs"
                      >
                        <option value="">Uncategorized</option>
                        {categories.filter((category) => category.active).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                      </select> : <button
                        disabled={bulkBusy || loading}
                        onClick={() => transaction.type === "expense" || transaction.type === "transfer" ? setCategoryEditingId(transaction.id) : setEditing(transaction)}
                        className="rounded py-1 text-left hover:text-primary hover:underline"
                        aria-label={`Edit category for ${transaction.merchant}`}
                      >{transaction.budget_category_name ?? categories.find((category) => category.id === transaction.budget_category_id)?.name ?? (transaction.type === "expense" ? "Uncategorized" : transaction.type === "credit_card_payment" ? "Card payment" : transaction.type === "income" ? "Income" : "No budget category")}</button>}
                      {transaction.ignored_from_budget && <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[10px]">Excluded from budget</span>}
                      {transaction.type === "transfer" && Number(transaction.amount) > 0 && transaction.budget_category_id && !transaction.ignored_from_budget && <span className="ml-2 rounded bg-positive/10 px-1.5 py-0.5 text-[10px] text-positive">Reimbursement</span>}
                    </td>
                    <td className="hidden px-4 py-2.5 text-muted-foreground md:table-cell">{transaction.account_name ?? accountNameById.get(transaction.account_id) ?? "Account"}{transaction.account_archived ? " (disconnected)" : ""}</td>
                    <td className="hidden px-4 py-2.5 capitalize text-muted-foreground lg:table-cell">{transaction.type}</td>
                    <td className={cn("whitespace-nowrap px-4 py-2.5 text-right font-mono font-medium tabular-nums", Number(transaction.amount) >= 0 ? "text-positive" : "text-foreground")}>
                      {formatCurrency(Number(transaction.amount), { sign: true })}
                    </td>
                  </tr>
                ))}
                {!loading && result?.data.length === 0 && (
                  <tr><td colSpan={7} className="px-4 py-10 text-center text-sm text-muted-foreground">No matching transactions.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-end gap-2 border-t border-border p-3">
            <Button variant="outline" size="sm" onClick={() => setPage((current) => current - 1)} disabled={page === 0 || loading || bulkBusy}><ChevronLeft /> Previous</Button>
            <Button variant="outline" size="sm" onClick={() => setPage((current) => current + 1)} disabled={loading || bulkBusy || last >= total}>Next <ChevronRight /></Button>
          </div>
        )}
      </Panel>
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
