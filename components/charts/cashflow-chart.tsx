"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatCurrency } from "@/lib/data";
import { useCashflowSeries } from "@/lib/data-provider";
import type { CashflowPoint } from "@/lib/data";
import { ChartTooltip } from "./chart-tooltip";

export function CashflowChart({ data, onSelect }: { data?: CashflowPoint[]; onSelect?: (point: CashflowPoint, direction: "inflow" | "outflow") => void }) {
  const cashflowSeries = useCashflowSeries();
  const points = (data ?? cashflowSeries).map((point) => ({ ...point,
    month: `${point.month}${point.incomplete ? " MTD" : ""}${point.available === false ? " —" : ""}`,
    income: point.available === false ? null : point.income,
    expenses: point.available === false ? null : point.expenses,
  }));
  return (
    <div className="h-[220px] w-full px-2 pb-2 pt-4">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={points}
          margin={{ top: 4, right: 12, left: 4, bottom: 0 }}
          barGap={4}
        >
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
            cursor={{ fill: "var(--muted)", opacity: 0.5 }}
            content={<ChartTooltip formatter={(v) => formatCurrency(v)} />}
          />
          <Bar
            dataKey="income"
            name="Income"
            fill="var(--chart-1)"
            radius={[2, 2, 0, 0]}
            maxBarSize={22}
            cursor={onSelect ? "pointer" : undefined}
            onClick={(entry) => onSelect?.((entry as unknown as { payload: CashflowPoint }).payload, "inflow")}
          />
          <Bar
            dataKey="expenses"
            name="Expenses"
            fill="var(--chart-4)"
            radius={[2, 2, 0, 0]}
            maxBarSize={22}
            cursor={onSelect ? "pointer" : undefined}
            onClick={(entry) => onSelect?.((entry as unknown as { payload: CashflowPoint }).payload, "outflow")}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
