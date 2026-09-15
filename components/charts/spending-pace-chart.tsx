"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ApiBudgetSummary } from "@/lib/api-client";
import { formatCurrency } from "@/lib/data";
import { Panel, PanelHeader } from "@/components/panel";

export function SpendingPaceChart({ summary, month, budget, loading }: { summary: ApiBudgetSummary | null; month: string; budget: number; loading: boolean }) {
  const [year, monthNumber] = month.split("-").map(Number);
  const label = new Date(year, monthNumber - 1, 1).toLocaleDateString("en-US", { month: "short" });
  const previousLabel = new Date(year, monthNumber - 2, 1).toLocaleDateString("en-US", { month: "short" });
  const current = summary?.daily_spending ?? [];
  const previous = summary?.previous_daily_spending ?? [];
  const points = Array.from({ length: Math.max(current.length, previous.length) }, (_, index) => ({ day: index + 1,
    current: current[index] == null ? null : Number(current[index]),
    previous: previous[index] == null ? null : Number(previous[index]),
  }));
  const comparable = points.filter((point) => point.current !== null && point.previous !== null);
  const last = comparable[comparable.length - 1];
  const difference = last ? last.current! - last.previous! : null;
  const anyData = points.some((point) => point.current !== null || point.previous !== null);
  return <Panel>
    <PanelHeader title="Spending through the month" description={`${label} compared with ${previousLabel} · includes pending spending and reimbursements`} />
    <div className="px-4 pt-3 text-sm">
      {loading ? "Loading spending history…" : difference !== null ? <><strong className="tabular-nums">{formatCurrency(Math.abs(difference))} {difference > 0 ? "more" : difference < 0 ? "less" : "difference"}</strong><span className="text-muted-foreground"> than {previousLabel} through day {last.day}</span></> : <span className="text-muted-foreground">No comparable history for these months.</span>}
    </div>
    <div className="h-64 px-2 pt-3">
      {!loading && anyData ? <ResponsiveContainer width="100%" height="100%"><LineChart data={points} margin={{ top: 20, right: 24, left: 5, bottom: 5 }}>
        <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 4" />
        <XAxis dataKey="day" ticks={[1, 5, 10, 15, 20, 25, points.length]} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
        <YAxis width={65} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickFormatter={(value) => formatCurrency(Number(value), { compact: true })} />
        <Tooltip labelFormatter={(day) => `Through day ${day}`} formatter={(value) => formatCurrency(Number(value))} contentStyle={{ background: "var(--popover)", borderColor: "var(--border)", borderRadius: 8, fontSize: 12 }} />
        {budget > 0 && <ReferenceLine y={budget} ifOverflow="extendDomain" stroke="var(--muted-foreground)" strokeDasharray="5 5" label={{ value: `${formatCurrency(budget)} budget`, position: "insideTopRight", fontSize: 11, fill: "var(--muted-foreground)" }} />}
        <Line type="linear" dataKey="current" name={label} stroke="var(--chart-1)" strokeWidth={2.5} dot={false} connectNulls={false} isAnimationActive={false} />
        <Line type="linear" dataKey="previous" name={previousLabel} stroke="var(--muted-foreground)" strokeDasharray="5 5" dot={false} connectNulls={false} isAnimationActive={false} />
      </LineChart></ResponsiveContainer> : <p className="flex h-full items-center justify-center text-sm text-muted-foreground">{loading ? "Loading…" : "Spending history is unavailable."}</p>}
    </div>
    <div className="flex gap-4 px-4 py-2 text-xs text-muted-foreground"><span>{label} — solid</span><span>{previousLabel} — dashed</span></div>
    <p className="px-4 pb-3 text-xs text-muted-foreground">Data as of {summary?.as_of ?? "today"}. Imported history may be partial; shorter months stop on their last day. Budget limits use your current category settings.</p>
  </Panel>;
}
