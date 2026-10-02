"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { ArrowDownRight, ArrowLeft, ArrowUpRight, ChartNoAxesCombined, Landmark } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from "recharts";
import { PageContainer, PageHeader } from "@/components/page-container";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import { Panel, PanelHeader } from "@/components/panel";
import { ApiError, api, type ApiInvestmentDashboard, type ApiInvestmentHoldingHistory } from "@/lib/api-client";
import { formatCurrency } from "@/lib/data";
import { useDataGeneration } from "@/lib/data-provider";

const ASSET_CLASS_LABEL: Record<string, string> = {
  equity: "Equities",
  fixed_income: "Fixed income",
  real_estate: "Real estate",
  cash: "Cash",
  alternatives: "Alternatives",
};

function formatHistoryDate(value: string, includeYear = false) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", ...(includeYear ? { year: "numeric" as const } : {}) });
}

function formatQuoteDate(value: string) {
  const date = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(date.getTime()) ? null : date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

const HISTORY_RANGES = ["1D", "1M", "6M", "YTD", "All time"] as const;
type HistoryRange = typeof HISTORY_RANGES[number];

function localDateString(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function subtractCalendarMonths(date: Date, amount: number) {
  const result = new Date(date);
  const day = result.getDate();
  result.setDate(1);
  result.setMonth(result.getMonth() - amount);
  const lastDay = new Date(result.getFullYear(), result.getMonth() + 1, 0).getDate();
  result.setDate(Math.min(day, lastDay));
  return result;
}

function rangeStartDate(range: HistoryRange, now = new Date()): string | null {
  const start = new Date(now);
  if (range === "All time") return null;
  if (range === "YTD") return `${start.getFullYear()}-01-01`;
  if (range === "1M") return localDateString(subtractCalendarMonths(start, 1));
  if (range === "6M") return localDateString(subtractCalendarMonths(start, 6));
  return localDateString(start);
}

type HoldingSelection = { accountId: string; accountName: string; symbol: string | null };

export default function InvestmentsPage() {
  const dataGeneration = useDataGeneration();
  const [dashboard, setDashboard] = useState<ApiInvestmentDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedHolding, setSelectedHolding] = useState<HoldingSelection | null>(null);
  const [historyRange, setHistoryRange] = useState<HistoryRange>("YTD");
  const [holdingHistory, setHoldingHistory] = useState<ApiInvestmentHoldingHistory | null>(null);
  const [holdingHistoryLoading, setHoldingHistoryLoading] = useState(false);
  const [holdingHistoryError, setHoldingHistoryError] = useState<string | null>(null);
  const [historyRequest, setHistoryRequest] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api.investments.dashboard()
      .then((data) => { if (!cancelled) setDashboard(data); })
      .catch((err) => { if (!cancelled) setError(err instanceof ApiError ? err.message : "Couldn't load your investments."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [dataGeneration]);

  useEffect(() => {
    if (!selectedHolding) return;
    let cancelled = false;
    (selectedHolding.symbol
      ? api.investments.holdingHistory(selectedHolding.accountId, selectedHolding.symbol)
      : api.investments.accountHistory(selectedHolding.accountId).then((data) => ({ ...data, symbol: "", last_price: null, price_as_of: null })))
      .then((data) => { if (!cancelled) setHoldingHistory(data); })
      .catch((err) => { if (!cancelled) setHoldingHistoryError(err instanceof ApiError ? err.message : "Couldn't load this investment history."); })
      .finally(() => { if (!cancelled) setHoldingHistoryLoading(false); });
    return () => { cancelled = true; };
  }, [selectedHolding, dataGeneration, historyRequest]);

  const selectHolding = (holding: ApiInvestmentDashboard["holdings"][number]) => {
    if (selectedHolding?.accountId === holding.account_id && selectedHolding.symbol === holding.symbol) {
      showTotal();
      return;
    }
    setHoldingHistory(null);
    setHoldingHistoryError(null);
    setHoldingHistoryLoading(true);
    setSelectedHolding({ accountId: holding.account_id, accountName: holding.account_name, symbol: holding.symbol });
    document.getElementById("investment-value-chart")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  };

  const showTotal = () => {
    setSelectedHolding(null);
    setHoldingHistory(null);
    setHoldingHistoryError(null);
    setHoldingHistoryLoading(false);
  };

  const selectAccount = (account: { id: string; name: string }) => {
    if (selectedHolding?.accountId === account.id && selectedHolding.symbol === null) {
      showTotal();
      return;
    }
    setHoldingHistory(null);
    setHoldingHistoryError(null);
    setHoldingHistoryLoading(true);
    setSelectedHolding({ accountId: account.id, accountName: account.name, symbol: null });
    document.getElementById("investment-value-chart")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  };
  const accountGroups = useMemo(() => {
    const groups = new Map((dashboard?.accounts ?? []).map((account) => [account.id, { ...account, holdings: [] as ApiInvestmentDashboard["holdings"] }]));
    for (const holding of dashboard?.holdings ?? []) {
      if (!groups.has(holding.account_id)) groups.set(holding.account_id, { id: holding.account_id, name: holding.account_name, type: "investment", balance: "0", institution: null, updated_at: null, holdings: [] });
      groups.get(holding.account_id)!.holdings.push(holding);
    }
    return [...groups.values()].map((group) => dashboard?.accounts.some((account) => account.id === group.id) ? group : { ...group, balance: String(group.holdings.reduce((sum, holding) => sum + Number(holding.market_value), 0)) });
  }, [dashboard]);
  const selectedAccount = accountGroups.find((account) => account.id === selectedHolding?.accountId);
  const selectedPosition = selectedHolding && dashboard?.holdings.find((holding) =>
    holding.account_id === selectedHolding.accountId && holding.symbol === selectedHolding.symbol);
  const matchingHoldingHistory = selectedHolding && holdingHistory?.account_id === selectedHolding.accountId && holdingHistory.symbol === (selectedHolding.symbol ?? "")
    ? holdingHistory
    : null;

  const history = useMemo(() => (dashboard?.history ?? []).map((point) => ({
    ...point,
    value: Number(point.value),
    label: formatHistoryDate(point.date),
  })), [dashboard]);
  const positionHistory = (matchingHoldingHistory?.history ?? []).map((point) => ({
    ...point,
    value: Number(point.value),
    label: formatHistoryDate(point.date, historyRange === "All time"),
  }));
  const availableHistory = selectedHolding ? positionHistory : history;
  const rangeStart = rangeStartDate(historyRange);
  const datedHistory = availableHistory.filter((point) => point.date <= localDateString(new Date()));
  // A daily snapshot may skip weekends, holidays, or days without an account sync.
  const chartHistory = historyRange === "1D"
    ? datedHistory.slice(-2)
    : datedHistory.filter((point) => rangeStart == null || point.date >= rangeStart);
  const chartValue = selectedHolding ? Number(positionHistory.at(-1)?.value ?? selectedPosition?.market_value ?? selectedAccount?.balance ?? 0) : Number(dashboard?.total_value ?? 0);
  const chartFirstValue = chartHistory[0]?.value;
  const chartLastValue = chartHistory.at(-1)?.value;
  const chartChange = chartHistory.length > 1 && chartFirstValue != null && chartLastValue != null ? chartLastValue - chartFirstValue : null;
  const selectedPrice = [
    selectedPosition?.last_price != null ? { value: selectedPosition.last_price, asOf: selectedPosition.price_as_of } : null,
    matchingHoldingHistory?.last_price != null ? { value: matchingHoldingHistory.last_price, asOf: matchingHoldingHistory.price_as_of } : null,
  ].filter((quote): quote is { value: string; asOf: string | null } => quote !== null)
    .reduce<{ value: string; asOf: string | null } | null>((latest, quote) =>
      latest === null || (quote.asOf !== null && (latest.asOf === null || quote.asOf > latest.asOf)) ? quote : latest, null);
  const selectedPriceDate = selectedPrice?.asOf ? formatQuoteDate(selectedPrice.asOf) : null;
  const totalValue = Number(dashboard?.total_value ?? 0);
  const gainLoss = Number(dashboard?.total_gain_loss ?? 0);
  const firstValue = history[0]?.value ?? totalValue;
  const valueChange = history.length > 1 ? totalValue - firstValue : null;
  const valueChangePercent = valueChange != null && firstValue > 0 ? valueChange / firstValue * 100 : null;

  return (
    <PageContainer>
      <PageHeader title="Investments" description="Your brokerage and retirement accounts, current positions, and value over time." />
      {error && <p role="alert" className="mb-4 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</p>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Investment account balances" value={loading ? "—" : formatCurrency(totalValue)} detail={loading ? "Loading accounts…" : `${dashboard?.account_count ?? 0} brokerage and retirement accounts, including cash`} icon={<Landmark className="size-4" />} />
        <Metric label="Account balance change" value={loading ? "—" : valueChange == null ? "Building history" : formatCurrency(valueChange, { sign: true })} detail={loading ? "Loading history…" : valueChangePercent == null ? "Records after each account sync" : `${valueChangePercent >= 0 ? "+" : ""}${valueChangePercent.toFixed(1)}% since first record`} positive={valueChange == null ? undefined : valueChange >= 0} icon={valueChange != null && valueChange < 0 ? <ArrowDownRight className="size-4" /> : <ArrowUpRight className="size-4" />} />
        <Metric label="Reported holdings value" value={loading ? "—" : formatCurrency(Number(dashboard?.total_holdings_value ?? 0))} detail={loading ? "Loading holdings…" : `${dashboard?.holding_count ?? 0} reported positions, including cash holdings`} icon={<ChartNoAxesCombined className="size-4" />} />
        <Metric label="Unrealized gain / loss" value={dashboard?.total_gain_loss != null ? formatCurrency(gainLoss, { sign: true }) : "—"} detail={loading ? "Loading positions…" : dashboard?.total_gain_loss != null ? `vs. ${formatCurrency(Number(dashboard.total_cost_basis))} known cost basis; excludes cash and missing basis` : "No non-cash positions with known cost basis"} positive={dashboard?.total_gain_loss != null ? gainLoss >= 0 : undefined} />
      </div>
      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">Account balances and reported holdings are two views of the same portfolio; do not add them together. Differences can reflect cash, unreported positions, or update times.{dashboard && Number(dashboard.excluded_gain_loss_value ?? 0) > 0 ? ` ${formatCurrency(Number(dashboard.excluded_gain_loss_value))} in cash or positions without cost basis is excluded from gain/loss.` : ""}</p>

      <Panel id="investment-value-chart" className="mt-4 scroll-mt-20">
        <PanelHeader
          title={selectedHolding ? `${selectedHolding.symbol ?? selectedHolding.accountName} value` : "Investment value"}
          description={selectedHolding ? `${selectedHolding.accountName} · ${selectedHolding.symbol ? "position market value over time" : "all investments · daily account balances"}` : "All brokerage and retirement accounts · daily account balances"}
          actions={selectedHolding && <button type="button" onClick={showTotal} className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><ArrowLeft className="size-3.5" /> Back to total</button>}
        />
        <div className="flex flex-wrap items-start justify-between gap-4 px-4 pt-4">
          <div>
            <p className="text-[11px] text-muted-foreground">{selectedHolding?.symbol ? "Current position value" : "Current account balance"}</p>
            <p className="font-mono text-2xl font-semibold tabular-nums text-foreground">{loading || (selectedHolding && !selectedPosition && holdingHistoryLoading) ? "—" : formatCurrency(chartValue)}</p>
          </div>
          {(selectedHolding || chartChange !== null) && <div className="ml-auto text-right">
            {selectedHolding?.symbol && <div>
              <p className="text-[11px] text-muted-foreground">Latest asset price</p>
              <p className="font-mono text-2xl font-semibold tabular-nums text-foreground">{selectedPrice ? formatCurrency(Number(selectedPrice.value)) : "—"}</p>
              <p className="text-[11px] text-muted-foreground">{selectedPrice ? selectedPriceDate ? `Price as of ${selectedPriceDate}` : "Price date unavailable" : holdingHistoryLoading ? "Loading latest price…" : "No price is available for this position."}</p>
            </div>}
            {chartChange !== null && <p className={`font-mono text-sm tabular-nums ${selectedHolding ? "mt-2" : ""} ${chartChange >= 0 ? "text-positive" : "text-destructive"}`}>{formatCurrency(chartChange, { sign: true })} since {formatHistoryDate(chartHistory[0].date)}</p>}
          </div>}
        </div>
        <div className="flex flex-wrap items-center gap-1 px-4 pt-4" role="group" aria-label={selectedHolding?.symbol ? "Position value history range" : "Investment value history range"}>{HISTORY_RANGES.map((range) => <button key={range} type="button" aria-pressed={historyRange === range} onClick={() => setHistoryRange(range)} className={`rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${historyRange === range ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>{range}</button>)}</div>
        <div className="h-72 p-4">{loading ? <div role="status" className="flex h-full items-center justify-center text-sm text-muted-foreground">Loading investment history…</div> : selectedHolding && holdingHistoryLoading ? <div role="status" className="flex h-full items-center justify-center text-sm text-muted-foreground">Loading {selectedHolding.symbol ?? selectedHolding.accountName} history…</div> : selectedHolding && holdingHistoryError ? <div className="flex h-full flex-col items-center justify-center gap-2 text-center"><p role="alert" className="text-sm text-destructive">{holdingHistoryError}</p><button type="button" className="text-xs font-medium text-primary hover:underline" onClick={() => { setHoldingHistoryError(null); setHoldingHistoryLoading(true); setHistoryRequest((value) => value + 1); }}>Try again</button></div> : chartHistory.length > 1 ? <ResponsiveContainer width="100%" height="100%"><LineChart data={chartHistory} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}><CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" /><XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} minTickGap={32} /><YAxis width={72} tickLine={false} axisLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} tickFormatter={(value) => formatCurrency(Number(value), { compact: true })} /><Tooltip content={({ active, payload, label }) => <ChartTooltip active={active} payload={payload as TooltipProps<number, string>["payload"]} label={String(payload?.[0]?.payload?.date ?? label ?? "")} formatter={(value) => formatCurrency(value)} />} /><Line type="monotone" dataKey="value" name={selectedHolding ? selectedHolding.symbol ?? selectedHolding.accountName : "Investment value"} stroke="var(--chart-1)" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} /></LineChart></ResponsiveContainer> : <div className="flex h-full flex-col items-center justify-center text-center"><p className="text-sm font-medium text-foreground">{selectedHolding && chartHistory.length === 0 ? "No values in this range" : selectedHolding ? formatCurrency(chartHistory[0].value) : dashboard?.account_count ? formatCurrency(totalValue) : "No investment accounts yet"}</p><p className="mt-1 max-w-md text-[12px] text-muted-foreground">{selectedHolding ? chartHistory.length === 0 ? "No daily value is recorded for this period. Try a longer range." : chartHistory.length === 1 ? `Recorded ${formatHistoryDate(chartHistory[0].date, true)}. This ${selectedHolding.symbol ? "position" : "account"}'s graph needs at least two dated values.` : "" : dashboard?.account_count ? "This is today’s value. Connect or sync your accounts on future days to build a value chart." : "Connect a brokerage or retirement account to see its balance, holdings, allocation, and value history here."}</p></div>}</div>
        <p className="border-t border-border px-4 py-2.5 text-[11px] text-muted-foreground">{selectedHolding?.symbol ? "This chart shows position value, which changes with price and quantity. History is recorded daily; intraday values are not available." : "Account balance changes include deposits and withdrawals; they are not investment returns."}</p>
      </Panel>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2">
          <PanelHeader title="Positions" description="Select an account or a position to view its value history. Select it again to return to the total. A dash means cost basis is unavailable or gain/loss is excluded for cash." />
          {accountGroups.length ? <div className="overflow-x-auto"><table className="w-full border-collapse text-[13px]">
            <thead><tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-2">Investment</th>
              <th className="px-4 py-2 text-right">Quantity</th><th className="hidden px-4 py-2 text-right lg:table-cell">Cost basis</th>
              <th className="px-4 py-2 text-right">Value</th><th className="hidden px-4 py-2 text-right sm:table-cell">Gain / loss</th>
            </tr></thead>
            <tbody>{accountGroups.map((account) => <Fragment key={account.id}>
              <tr onClick={() => selectAccount(account)} className={`cursor-pointer border-b border-border bg-muted/30 transition-colors hover:bg-muted/60 ${selectedHolding?.accountId === account.id && selectedHolding.symbol === null ? "bg-primary/10" : ""}`}>
                <td className="px-4 py-3" colSpan={2}><button type="button" aria-label={`View ${account.name} account chart`} aria-pressed={selectedHolding?.accountId === account.id && selectedHolding.symbol === null} onClick={(event) => { event.stopPropagation(); selectAccount(account); }} className="inline-flex items-center gap-2 rounded-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><Landmark className="size-4 text-muted-foreground" />{account.name}</button><p className="mt-1 text-[11px] text-muted-foreground">{account.holdings.length} positions</p></td>
                <td className="hidden lg:table-cell" />
                <td className="px-4 py-3 text-right font-mono font-semibold tabular-nums">{formatCurrency(Number(account.balance))}</td>
                <td className="hidden sm:table-cell" />
              </tr>
              {account.holdings.map((holding) => { const selected = selectedHolding?.accountId === holding.account_id && selectedHolding.symbol === holding.symbol; return <tr key={`${holding.account_id}-${holding.symbol}`} onClick={() => selectHolding(holding)} className={`cursor-pointer border-b border-border/60 transition-colors last:border-0 hover:bg-muted/50 ${selected ? "bg-primary/5" : ""}`}>
              <td className="py-3 pl-10 pr-4"><button type="button" aria-label={`View ${holding.symbol} in ${holding.account_name} chart`} aria-pressed={selected} onClick={(event) => { event.stopPropagation(); selectHolding(holding); }} className="group inline-flex items-center gap-2 rounded-sm text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><span><span className={`block font-medium ${selected ? "text-primary" : "text-foreground group-hover:text-primary"}`}>{holding.symbol}</span><span className="block text-[11px] capitalize text-muted-foreground">{ASSET_CLASS_LABEL[holding.asset_class] ?? holding.asset_class}</span></span><ChartNoAxesCombined className="size-3.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" /></button></td>
              <td className="px-4 py-3 text-right font-mono tabular-nums">{Number(holding.quantity).toLocaleString("en-US", { maximumFractionDigits: 4 })}</td>
              <td className="hidden px-4 py-3 text-right font-mono tabular-nums text-muted-foreground lg:table-cell">{holding.cost_basis == null ? "—" : formatCurrency(Number(holding.cost_basis))}</td>
              <td className="px-4 py-3 text-right font-mono font-medium tabular-nums text-foreground">{formatCurrency(Number(holding.market_value))}</td>
              <td className={`hidden px-4 py-3 text-right font-mono tabular-nums sm:table-cell ${holding.gain_loss == null ? "text-muted-foreground" : Number(holding.gain_loss) >= 0 ? "text-positive" : "text-destructive"}`}>{holding.gain_loss == null ? "—" : formatCurrency(Number(holding.gain_loss), { sign: true })}</td>
            </tr>; })}
            </Fragment>)}</tbody>
          </table></div> : <p className="p-5 text-sm text-muted-foreground">{loading ? "Loading holdings…" : "No holdings were reported. Accounts linked before Investments access was enabled must be unlinked and linked again, then synced. Some institutions do not provide holdings through Plaid."}</p>}
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel>
            <PanelHeader title="Allocation" description="Based on the market value of reported holdings." />
            {dashboard?.allocation.length ? <div className="space-y-3 p-4">{dashboard.allocation.map((item) => { const weight = Number(item.weight) * 100; return <div key={item.asset_class}><div className="flex justify-between gap-3 text-[12px]"><span className="text-foreground">{ASSET_CLASS_LABEL[item.asset_class] ?? item.asset_class}</span><span className="font-mono text-muted-foreground">{weight.toFixed(1)}%</span></div><div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary" style={{ width: `${weight}%` }} /></div><p className="mt-1 text-right font-mono text-[11px] text-muted-foreground">{formatCurrency(Number(item.market_value))}</p></div>; })}</div> : <p className="p-5 text-sm text-muted-foreground">{loading ? "Loading allocation…" : "Allocation will appear when account holdings are available."}</p>}
          </Panel>
          <Panel>
            <PanelHeader title="Investment accounts" description="Included in the value chart above." />
            {dashboard?.accounts.length ? <div className="divide-y divide-border">{dashboard.accounts.map((account) => <button type="button" key={account.id} onClick={() => selectAccount(account)} aria-pressed={selectedHolding?.accountId === account.id && selectedHolding.symbol === null} className="flex w-full items-center justify-between gap-3 p-4 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><div className="min-w-0"><p className="truncate text-[13px] font-medium text-foreground">{account.name}</p><p className="mt-0.5 text-[11px] capitalize text-muted-foreground">{account.institution ?? account.type}</p></div><p className="font-mono text-[13px] font-medium tabular-nums text-foreground">{formatCurrency(Number(account.balance))}</p></button>)}</div> : <p className="p-5 text-sm text-muted-foreground">{loading ? "Loading accounts…" : "No brokerage or retirement accounts are connected."}</p>}
          </Panel>
        </div>
      </div>
    </PageContainer>
  );
}

function Metric({ label, value, detail, positive, icon }: { label: string; value: string; detail: string; positive?: boolean; icon?: React.ReactNode }) {
  return <Panel><div className="flex items-start justify-between gap-3 p-4"><div><p className="text-[12px] text-muted-foreground">{label}</p><p className={positive === undefined ? "mt-1 font-mono text-xl font-semibold tabular-nums text-foreground" : positive ? "mt-1 font-mono text-xl font-semibold tabular-nums text-positive" : "mt-1 font-mono text-xl font-semibold tabular-nums text-destructive"}>{value}</p><p className="mt-1 text-[11px] text-muted-foreground">{detail}</p></div>{icon && <span className="rounded-md bg-muted p-2 text-muted-foreground">{icon}</span>}</div></Panel>;
}
