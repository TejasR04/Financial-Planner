"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { netWorthSeries, formatCurrency } from "@/lib/data";
import { ChartTooltip } from "./chart-tooltip";

export function NetWorthChart() {
  return (
    <div className="h-[280px] w-full px-2 pb-2 pt-4">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={netWorthSeries}
          margin={{ top: 4, right: 12, left: 4, bottom: 0 }}
        >
          <defs>
            <linearGradient id="nw-net" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.22} />
              <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="2 4"
            stroke="var(--border)"
            vertical={false}
          />
          <XAxis
            dataKey="month"
            tickLine={false}
            axisLine={false}
            tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
            dy={6}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            width={44}
            tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
            tickFormatter={(v) => formatCurrency(v, { compact: true })}
          />
          <Tooltip
            cursor={{ stroke: "var(--border)", strokeWidth: 1 }}
            content={<ChartTooltip formatter={(v) => formatCurrency(v)} />}
          />
          <Area
            type="monotone"
            dataKey="net"
            name="Net Worth"
            stroke="var(--chart-1)"
            strokeWidth={2}
            fill="url(#nw-net)"
            dot={false}
            activeDot={{ r: 3, strokeWidth: 0 }}
          />
          <Area
            type="monotone"
            dataKey="assets"
            name="Assets"
            stroke="var(--chart-2)"
            strokeWidth={1.25}
            strokeDasharray="3 3"
            fill="none"
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
