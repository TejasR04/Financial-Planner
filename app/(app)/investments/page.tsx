"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, ChartNoAxesCombined, Landmark } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PageContainer, PageHeader } from "@/components/page-container";
import { Panel, PanelHeader } from "@/components/panel";
import { ApiError, api, type ApiInvestmentDashboard } from "@/lib/api-client";
import { formatCurrency } from "@/lib/data";

const ASSET_CLASS_LABEL: Record<string, string> = {
  equity: "Equities",
  fixed_income: "Fixed income",
  real_estate: "Real estate",
  cash: "Cash",
  alternatives: "Alternatives",
};

function formatHistoryDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default function InvestmentsPage() {
  const [dashboard, setDashboard] = useState<ApiInvestmentDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api.investments.dashboard()
      .then((data) => { if (!cancelled) setDashboard(data); })
      .catch((err) => { if (!cancelled) setError(err instanceof ApiError ? err.message : "Couldn't load your investments."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const history = useMemo(() => (dashboard?.history ?? []).map((point) => ({
    ...point,
    value: Number(point.value),
    label: formatHistoryDate(point.date),
  })), [dashboard]);
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
        <Metric label="Invested value" value={loading ? "—" : formatCurrency(totalValue)} detail={`${dashboard?.account_count ?? 0} accounts`} icon={<Landmark className="size-4" />} />
        <Metric label="Value change" value={valueChange == null ? "Building history" : formatCurrency(valueChange, { sign: true })} detail={valueChangePercent == null ? "Records after each account sync" : `${valueChangePercent >= 0 ? "+" : ""}${valueChangePercent.toFixed(1)}% since first record`} positive={valueChange == null ? undefined : valueChange >= 0} icon={valueChange != null && valueChange < 0 ? <ArrowDownRight className="size-4" /> : <ArrowUpRight className="size-4" />} />
        <Metric label="Holdings value" value={loading ? "—" : formatCurrency(Number(dashboard?.total_holdings_value ?? 0))} detail={`${dashboard?.holding_count ?? 0} positions`} icon={<ChartNoAxesCombined className="size-4" />} />
        <Metric label="Unrealized gain / loss" value={dashboard && Number(dashboard.total_cost_basis) > 0 ? formatCurrency(gainLoss, { sign: true }) : "—"} detail={dashboard && Number(dashboard.total_cost_basis) > 0 ? `vs. ${formatCurrency(Number(dashboard.total_cost_basis))} cost basis` : "Cost basis not available"} positive={dashboard && Number(dashboard.total_cost_basis) > 0 ? gainLoss >= 0 : undefined} />
      </div>

      <Panel className="mt-4">
        <PanelHeader title="Investment value" description={history.length > 1 ? "Daily value across brokerage and retirement accounts." : "Your chart will build from daily account syncs."} />
        <div className="h-72 p-4">{history.length > 1 ? <ResponsiveContainer width="100%" height="100%"><LineChart data={history} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}><CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" /><XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} minTickGap={32} /><YAxis width={72} tickLine={false} axisLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} tickFormatter={(value) => formatCurrency(Number(value), { compact: true })} /><Tooltip formatter={(value) => formatCurrency(Number(value))} labelFormatter={(_, points) => points?.[0]?.payload.date ?? ""} /><Line type="monotone" dataKey="value" name="Investment value" stroke="var(--chart-1)" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} /></LineChart></ResponsiveContainer> : <div className="flex h-full flex-col items-center justify-center text-center"><p className="text-sm font-medium text-foreground">{dashboard?.account_count ? formatCurrency(totalValue) : "No investment accounts yet"}</p><p className="mt-1 max-w-md text-[12px] text-muted-foreground">{dashboard?.account_count ? "This is today’s value. Connect or sync your accounts on future days to build a real performance chart." : "Connect a brokerage or retirement account to see its balance, holdings, allocation, and value history here."}</p></div>}</div>
      </Panel>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2">
          <PanelHeader title="Positions" description="Individual investments reported by your connected accounts." />
          {dashboard?.holdings.length ? <div className="overflow-x-auto"><table className="w-full border-collapse text-[13px]"><thead><tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground"><th className="px-4 py-2">Investment</th><th className="hidden px-4 py-2 md:table-cell">Account</th><th className="px-4 py-2 text-right">Quantity</th><th className="hidden px-4 py-2 text-right lg:table-cell">Cost basis</th><th className="px-4 py-2 text-right">Value</th><th className="hidden px-4 py-2 text-right sm:table-cell">Gain / loss</th></tr></thead><tbody>{dashboard.holdings.map((holding) => <tr key={`${holding.account_id}-${holding.symbol}`} className="border-b border-border/60 last:border-0"><td className="px-4 py-3"><p className="font-medium text-foreground">{holding.symbol}</p><p className="text-[11px] capitalize text-muted-foreground">{ASSET_CLASS_LABEL[holding.asset_class] ?? holding.asset_class}</p></td><td className="hidden px-4 py-3 text-muted-foreground md:table-cell">{holding.account_name}</td><td className="px-4 py-3 text-right font-mono tabular-nums">{Number(holding.quantity).toLocaleString("en-US", { maximumFractionDigits: 4 })}</td><td className="hidden px-4 py-3 text-right font-mono tabular-nums text-muted-foreground lg:table-cell">{formatCurrency(Number(holding.cost_basis))}</td><td className="px-4 py-3 text-right font-mono font-medium tabular-nums text-foreground">{formatCurrency(Number(holding.market_value))}</td><td className={Number(holding.gain_loss) >= 0 ? "hidden px-4 py-3 text-right font-mono tabular-nums text-positive sm:table-cell" : "hidden px-4 py-3 text-right font-mono tabular-nums text-destructive sm:table-cell"}>{formatCurrency(Number(holding.gain_loss), { sign: true })}</td></tr>)}</tbody></table></div> : <p className="p-5 text-sm text-muted-foreground">Positions will appear after your institution provides holdings through its next sync.</p>}
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel>
            <PanelHeader title="Allocation" description="Based on the market value of reported holdings." />
            {dashboard?.allocation.length ? <div className="space-y-3 p-4">{dashboard.allocation.map((item) => { const weight = Number(item.weight) * 100; return <div key={item.asset_class}><div className="flex justify-between gap-3 text-[12px]"><span className="text-foreground">{ASSET_CLASS_LABEL[item.asset_class] ?? item.asset_class}</span><span className="font-mono text-muted-foreground">{weight.toFixed(1)}%</span></div><div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary" style={{ width: `${weight}%` }} /></div><p className="mt-1 text-right font-mono text-[11px] text-muted-foreground">{formatCurrency(Number(item.market_value))}</p></div>; })}</div> : <p className="p-5 text-sm text-muted-foreground">Allocation will appear when account holdings are available.</p>}
          </Panel>
          <Panel>
            <PanelHeader title="Investment accounts" description="Included in the value chart above." />
            {dashboard?.accounts.length ? <div className="divide-y divide-border">{dashboard.accounts.map((account) => <div key={account.id} className="flex items-center justify-between gap-3 p-4"><div className="min-w-0"><p className="truncate text-[13px] font-medium text-foreground">{account.name}</p><p className="mt-0.5 text-[11px] capitalize text-muted-foreground">{account.institution ?? account.type}</p></div><p className="font-mono text-[13px] font-medium tabular-nums text-foreground">{formatCurrency(Number(account.balance))}</p></div>)}</div> : <p className="p-5 text-sm text-muted-foreground">No brokerage or retirement accounts are connected.</p>}
          </Panel>
        </div>
      </div>
    </PageContainer>
  );
}

function Metric({ label, value, detail, positive, icon }: { label: string; value: string; detail: string; positive?: boolean; icon?: React.ReactNode }) {
  return <Panel><div className="flex items-start justify-between gap-3 p-4"><div><p className="text-[12px] text-muted-foreground">{label}</p><p className={positive === undefined ? "mt-1 font-mono text-xl font-semibold tabular-nums text-foreground" : positive ? "mt-1 font-mono text-xl font-semibold tabular-nums text-positive" : "mt-1 font-mono text-xl font-semibold tabular-nums text-destructive"}>{value}</p><p className="mt-1 text-[11px] text-muted-foreground">{detail}</p></div>{icon && <span className="rounded-md bg-muted p-2 text-muted-foreground">{icon}</span>}</div></Panel>;
}
