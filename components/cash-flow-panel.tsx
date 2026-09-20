"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { Panel, PanelHeader } from "./panel";
import { Button } from "./ui/button";
import { CashflowChart } from "./charts/cashflow-chart";
import { useCashflowSeries, useTransactionsData } from "@/lib/data-provider";
import { api } from "@/lib/api-client";
import { formatCurrency, type CashflowPoint } from "@/lib/data";
import { exportTransactionsCsv } from "@/lib/transaction-export";
import { CashFlowDetails } from "./cash-flow-details";

export function CashFlowPanel() {
  const actuals = useCashflowSeries();
  const transactions = useTransactionsData();
  const [months, setMonths] = useState<6 | 12>(12);
  const [mode, setMode] = useState<"actuals" | "outlook">("actuals");
  const [outlook, setOutlook] = useState<CashflowPoint[]>([]);
  const [note, setNote] = useState("Loading planning outlook…");
  const [loading, setLoading] = useState(false);
  const [details, setDetails] = useState<{ month: string; direction: "inflow" | "outflow" } | null>(null);
  const [reviewMonth, setReviewMonth] = useState("");
  useEffect(() => {
    if (mode !== "outlook") return;
    let cancelled = false;
    setLoading(true);
    setOutlook([]);
    setNote("Loading planning outlook…");
    api.simulations.cashFlow(months).then((result) => {
      if (cancelled) return;
      setOutlook(result.series.map((point) => {
        const today = new Date();
        const date = new Date(today.getFullYear(), today.getMonth() + point.month_index, 1);
        return { month: date.toLocaleDateString("en-US", { month: "short", year: "2-digit" }), income: Number(point.income), expenses: Number(point.expenses) };
      }));
      setNote(`${result.income_source} · ${result.expense_source}`);
    }).catch((error) => { if (!cancelled) setNote(error instanceof Error ? error.message : "Outlook unavailable."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [mode, months, transactions]);
  const visible = mode === "actuals" ? actuals.slice(-months) : outlook;
  const available = visible.filter((point) => point.available !== false);
  const completed = available.filter((point) => !point.incomplete && !point.partialHistory);
  const income = available.reduce((sum, point) => sum + point.income, 0);
  const expenses = available.reduce((sum, point) => sum + point.expenses, 0);
  const average = completed.length ? completed.reduce((sum, point) => sum + point.income - point.expenses, 0) / completed.length : null;
  const openTransactions = (point: CashflowPoint, direction: "inflow" | "outflow") => {
    if (!point.monthKey || point.available === false) return;
    setDetails({ month: point.monthKey, direction });
  };
  const exportRows = () => {
    const today = new Date();
    const cutoff = new Date(today.getFullYear(), today.getMonth() - months + 1, 1);
    exportTransactionsCsv(transactions.filter((row) => new Date(`${row.postedAt}T00:00:00`) >= cutoff), `meridian-transactions-last-${months}-months.csv`);
  };
  return <Panel>
    <PanelHeader title="Cash flow" description={mode === "actuals" ? "Budget-category spending, net of reimbursements · income outside the budget" : note} actions={<div className="flex flex-wrap items-center gap-2">
      <Button size="xs" variant={mode === "actuals" ? "outline" : "ghost"} onClick={() => setMode("actuals")}>Actuals</Button>
      <Button size="xs" variant={mode === "outlook" ? "outline" : "ghost"} onClick={() => setMode("outlook")}>Outlook</Button>
      <select aria-label="Cash-flow period" value={months} onChange={(event) => setMonths(Number(event.target.value) as 6 | 12)} className="h-7 rounded-md border border-border bg-background px-2 text-xs">
        <option value={6}>{mode === "actuals" ? "Last" : "Next"} 6 months</option><option value={12}>{mode === "actuals" ? "Last" : "Next"} 12 months</option>
      </select>
      {mode === "actuals" && <Button size="xs" variant="outline" onClick={exportRows}><Download />Export CSV</Button>}
    </div>} />
    <div className="flex gap-4 px-4 pt-3 text-xs text-muted-foreground"><span>● Income (blue)</span><span>● Expenses (orange)</span></div>
    {loading ? <p className="p-8 text-sm text-muted-foreground">Loading planning outlook…</p> : <CashflowChart data={visible} onSelect={mode === "actuals" ? openTransactions : undefined} />}
    {mode === "actuals" && available.length > 0 && <div className="flex flex-wrap items-center gap-2 px-4 pb-3">
      <select aria-label="Month to review" value={available.some((point) => point.monthKey === reviewMonth) ? reviewMonth : available.at(-1)?.monthKey ?? ""} onChange={(event) => setReviewMonth(event.target.value)} className="h-7 rounded-md border border-border bg-background px-2 text-xs">
        {available.map((point) => <option key={point.monthKey} value={point.monthKey}>{point.monthKey}</option>)}
      </select>
      {(["outflow", "inflow"] as const).map((direction) => <Button key={direction} size="xs" variant="outline" onClick={() => {
        const point = available.find((point) => point.monthKey === reviewMonth) ?? available.at(-1);
        if (point) openTransactions(point, direction);
      }}>View {direction === "outflow" ? "expenses" : "income"}</Button>)}
    </div>}
    <div className="grid grid-cols-2 divide-x divide-border border-t border-border lg:grid-cols-4">
      {[{ label: "Total income", value: income }, { label: "Total expenses", value: expenses }, { label: "Net cash flow", value: income - expenses }, { label: mode === "actuals" ? "Average per completed month" : "Average per projected month", value: average }].map((item) => <div key={item.label} className="p-4"><p className="text-xs text-muted-foreground">{item.label}</p><p className="mt-1 text-lg font-semibold tabular-nums">{available.length && item.value !== null ? formatCurrency(item.value) : "—"}</p></div>)}
    </div>
    {mode === "actuals" && <p className="border-t border-border px-4 py-2 text-xs text-muted-foreground">Expenses include assigned budget categories only, including pending activity. Refunds and categorized incoming transfers reduce spending; unassigned and ignored spending are excluded. Click a bar to review its transactions. MTD = month to date; the average excludes current and partial-history months. Account history may be partial.</p>}
    {details && <CashFlowDetails month={details.month} direction={details.direction} onClose={() => setDetails(null)} />}
  </Panel>;
}
