"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";
import { PageContainer, PageHeader } from "@/components/page-container";
import { Panel, PanelHeader } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { ApiError, api, type ApiTransactionList } from "@/lib/api-client";
import { formatCurrency } from "@/lib/data";
import { useAccountsData } from "@/lib/data-provider";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 50;

function formatDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function TransactionsPage() {
  const accounts = useAccountsData();
  const [accountId, setAccountId] = useState("");
  const [category, setCategory] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [page, setPage] = useState(0);
  const [result, setResult] = useState<ApiTransactionList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const accountNameById = useMemo(
    () => new Map(accounts.map((account) => [account.id, account.name])),
    [accounts],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.transactions
      .list({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        accountId: accountId || undefined,
        category: category.trim() || undefined,
        since: since || undefined,
        until: until || undefined,
      })
      .then((next) => {
        if (!cancelled) setResult(next);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Couldn't load transactions.");
          setResult(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [accountId, category, page, since, until]);

  const resetFilters = () => {
    setAccountId("");
    setCategory("");
    setSince("");
    setUntil("");
    setPage(0);
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
      />

      <Panel>
        <PanelHeader title="Filters" description="Narrow the ledger by account, category, or date" />
        <div className="grid grid-cols-1 gap-3 border-t border-border p-4 sm:grid-cols-2 xl:grid-cols-5">
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
          <input
            value={category}
            onChange={(event) => setFilterPage(() => setCategory(event.target.value))}
            placeholder="Category"
            className="h-8 rounded-md border border-border bg-background px-2 text-[12px] text-foreground outline-none placeholder:text-muted-foreground focus:border-ring"
          />
          <label className="flex items-center gap-2 text-[12px] text-muted-foreground">
            From
            <input type="date" value={since} onChange={(event) => setFilterPage(() => setSince(event.target.value))} className="h-8 min-w-0 flex-1 rounded-md border border-border bg-background px-2 text-foreground outline-none focus:border-ring" />
          </label>
          <label className="flex items-center gap-2 text-[12px] text-muted-foreground">
            To
            <input type="date" value={until} onChange={(event) => setFilterPage(() => setUntil(event.target.value))} className="h-8 min-w-0 flex-1 rounded-md border border-border bg-background px-2 text-foreground outline-none focus:border-ring" />
          </label>
          <Button variant="outline" size="sm" onClick={resetFilters} disabled={!accountId && !category && !since && !until}>
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
                      <span>{transaction.merchant}</span>
                      {transaction.status === "pending" && <span className="ml-2 rounded border border-warning/30 bg-warning/10 px-1 py-px text-[10px] font-medium text-warning">pending</span>}
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">{transaction.category}</td>
                    <td className="hidden px-4 py-2.5 text-muted-foreground md:table-cell">{accountNameById.get(transaction.account_id) ?? "Account"}</td>
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
    </PageContainer>
  );
}
