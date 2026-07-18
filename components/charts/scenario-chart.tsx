"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useScenariosData } from "@/lib/data-provider";
import { ChartTooltip } from "./chart-tooltip";

export function ScenarioChart({ activeIds }: { activeIds: string[] }) {
  const scenarios = useScenariosData();

  // Each scenario has its own real trajectory (different retirement ages
  // produce different-length runs), so build the shared x-axis as the
  // union of every scenario's calendar years rather than a fixed list.
  const years = Array.from(new Set(scenarios.flatMap((s) => s.years))).sort();
  const data = years.map((year) => {
    const row: Record<string, number | string> = { year };
    scenarios.forEach((s) => {
      const i = s.years.indexOf(year);
      if (i !== -1) row[s.name] = s.series[i];
    });
    return row;
  });

  return (
    <div className="h-[300px] w-full px-2 pb-2 pt-4">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 4, right: 16, left: 4, bottom: 0 }}
        >
          <CartesianGrid
            strokeDasharray="2 4"
            stroke="var(--border)"
            vertical={false}
          />
          <XAxis
            dataKey="year"
            tickLine={false}
            axisLine={false}
            tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
            dy={6}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            width={40}
            tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
            tickFormatter={(v) => `$${v}M`}
          />
          <Tooltip
            cursor={{ stroke: "var(--border)", strokeWidth: 1 }}
            content={
              <ChartTooltip
                formatter={(v) => `$${(v as number).toFixed(2)}M`}
              />
            }
          />
          {scenarios.map((s) => (
            <Line
              key={s.id}
              type="monotone"
              dataKey={s.name}
              stroke={s.color}
              strokeWidth={activeIds.includes(s.id) ? 2.25 : 1}
              strokeOpacity={activeIds.includes(s.id) ? 1 : 0.25}
              dot={false}
              activeDot={{ r: 3, strokeWidth: 0 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
