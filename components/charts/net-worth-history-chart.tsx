"use client";

import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from "recharts";
import { api, type ApiNetWorthHistoryPoint } from "@/lib/api-client";
import { formatCurrency } from "@/lib/data";
import { useDataGeneration } from "@/lib/data-provider";
import { ChartTooltip } from "./chart-tooltip";

function displayDate(value: string, year: "numeric" | "2-digit" = "numeric") {
  return new Date(`${value}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year });
}

export function NetWorthHistoryChart() {
  const generation = useDataGeneration();
  const [history, setHistory] = useState<ApiNetWorthHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.accounts.netWorthHistory()
      .then((rows) => { if (!cancelled) { setHistory(rows); setError(false); } })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [generation]);

  const points = useMemo(() => history.map((point) => ({
    date: point.date,
    timestamp: new Date(`${point.date}T12:00:00`).getTime(),
    assets: Number(point.assets),
    liabilities: Number(point.liabilities),
    net: Number(point.net),
  })), [history]);

  if (loading) return <div role="status" className="flex h-[280px] items-center justify-center text-sm text-muted-foreground">Loading net worth history…</div>;
  if (error) return <div role="alert" className="flex h-[280px] items-center justify-center text-sm text-destructive">Couldn’t load net worth history.</div>;
  if (points.length < 2) return <div className="flex h-[280px] flex-col items-center justify-center px-4 text-center">
    <p className="text-sm font-medium text-foreground">{points.length ? formatCurrency(points[0].net) : "No recorded net worth yet"}</p>
    <p className="mt-1 max-w-sm text-xs text-muted-foreground">{points.length
      ? `Recorded ${displayDate(points[0].date)}. The chart needs another recorded day to show how your net worth changed.`
      : "The chart will begin when your account totals are first recorded."}</p>
  </div>;

  return <div className="h-[280px] w-full px-2 pb-2 pt-4">
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={points} margin={{ top: 4, right: 12, left: 4, bottom: 0 }}>
        <defs><linearGradient id="nw-history-net" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.22} />
          <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
        </linearGradient></defs>
        <CartesianGrid strokeDasharray="2 4" stroke="var(--border)" vertical={false} />
        <XAxis dataKey="timestamp" type="number" scale="time" domain={["dataMin", "dataMax"]}
          tickFormatter={(value) => new Date(Number(value)).toLocaleDateString("en-US", { month: "short", year: "2-digit" })}
          tickLine={false} axisLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} minTickGap={24} dy={6} />
        <YAxis tickLine={false} axisLine={false} width={54} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} tickFormatter={(value) => formatCurrency(Number(value), { compact: true })} />
        <Tooltip cursor={{ stroke: "var(--border)", strokeWidth: 1 }} content={({ active, payload }) => <ChartTooltip
          active={active} payload={payload as TooltipProps<number, string>["payload"]}
          label={payload?.[0]?.payload?.date ? displayDate(String(payload[0].payload.date)) : ""}
          formatter={(value) => formatCurrency(value)}
        />} />
        <Area type="monotone" dataKey="net" name="Net Worth" stroke="var(--chart-1)" strokeWidth={2} fill="url(#nw-history-net)" dot={false} activeDot={{ r: 3, strokeWidth: 0 }} />
        <Area type="monotone" dataKey="liabilities" name="Liabilities" stroke="var(--chart-4)" strokeWidth={1.25} strokeDasharray="3 3" fill="none" dot={false} />
        <Area type="monotone" dataKey="assets" name="Assets" stroke="var(--chart-2)" strokeWidth={1.25} strokeDasharray="3 3" fill="none" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  </div>;
}
