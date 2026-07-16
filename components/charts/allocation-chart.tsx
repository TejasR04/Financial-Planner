"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { allocation, formatCurrency } from "@/lib/data";
import { ChartTooltip } from "./chart-tooltip";

export function AllocationChart() {
  const total = allocation.reduce((s, a) => s + a.amount, 0);

  return (
    <div className="flex items-center gap-4 p-4">
      <div className="relative h-[148px] w-[148px] shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={allocation}
              dataKey="value"
              nameKey="name"
              innerRadius={50}
              outerRadius={72}
              paddingAngle={2}
              strokeWidth={0}
              stroke="var(--card)"
            >
              {allocation.map((slice) => (
                <Cell key={slice.name} fill={slice.color} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip formatter={(v) => `${v}%`} />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[10px] text-muted-foreground">Total</span>
          <span className="font-mono text-sm font-semibold text-foreground tabular-nums">
            {formatCurrency(total, { compact: true })}
          </span>
        </div>
      </div>

      <ul className="flex-1 space-y-1.5">
        {allocation.map((slice) => (
          <li key={slice.name} className="flex items-center gap-2 text-[13px]">
            <span
              className="size-2.5 shrink-0 rounded-[3px]"
              style={{ background: slice.color }}
            />
            <span className="flex-1 text-foreground">{slice.name}</span>
            <span className="font-mono text-muted-foreground tabular-nums">
              {formatCurrency(slice.amount, { compact: true })}
            </span>
            <span className="w-9 text-right font-mono font-medium text-foreground tabular-nums">
              {slice.value}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
