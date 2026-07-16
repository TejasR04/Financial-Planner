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
import { scenarios, scenarioYears } from "@/lib/data";
import { ChartTooltip } from "./chart-tooltip";

export function ScenarioChart({ activeIds }: { activeIds: string[] }) {
  const data = scenarioYears.map((year, i) => {
    const row: Record<string, number | string> = { year };
    scenarios.forEach((s) => {
      row[s.name] = s.series[i];
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
