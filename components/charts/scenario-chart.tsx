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
import { displayProjectionDollars, type ProjectionDollarDisplay } from "@/lib/projection-dollars";

export function ScenarioChart({
  activeIds,
  dollarDisplay,
}: {
  activeIds: string[];
  dollarDisplay: ProjectionDollarDisplay;
}) {
  const scenarios = useScenariosData();
  const projectedScenarios = scenarios.filter(
    (scenario) => scenario.projectionStatus === "available" && scenario.years.length > 0,
  );

  // Each scenario has its own real trajectory (different retirement ages
  // produce different-length runs), so build the shared x-axis as the
  // union of every scenario's calendar years rather than a fixed list.
  const years = Array.from(new Set(projectedScenarios.flatMap((s) => s.years))).sort();
  const data = years.map((year) => {
    const row: Record<string, number | string> = { year };
    projectedScenarios.forEach((s) => {
      const i = s.years.indexOf(year);
      if (i === -1) return;
      const yearsFromToday = i + 1;
      const inflationRate = s.inflationRate;
      row[s.id] = displayProjectionDollars(s.series[i] * 1_000_000, yearsFromToday, inflationRate, dollarDisplay) / 1_000_000;
      row[`${s.id}-withdrawal`] = displayProjectionDollars(s.withdrawals[i], yearsFromToday, inflationRate, dollarDisplay);
      row[`${s.id}-retirement-age`] = year === s.retirementYear ? s.retirementAge : 0;
    });
    return row;
  });

  if (years.length === 0) {
    const loading = scenarios.some((scenario) => scenario.projectionStatus === "loading");
    return (
      <div className="flex h-[300px] items-center justify-center px-4 text-center text-[13px] text-muted-foreground">
        {loading ? "Loading scenario projections…" : "Scenario projections are unavailable. Try refreshing the projections page."}
      </div>
    );
  }

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
            width={48}
            tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
            tickFormatter={(v) => `$${v}M`}
          />
          <Tooltip
            cursor={{ stroke: "var(--border)", strokeWidth: 1 }}
            content={
              <ChartTooltip
                formatter={(v) => `$${(v as number).toFixed(2)}M`}
              detail={(entry) => {
                  const dataKey = String(entry.dataKey);
                  const withdrawal = Number(
                    (entry.payload as Record<string, number | string>)[`${dataKey}-withdrawal`] ?? 0,
                  );
                  const retirementAge = Number(
                    (entry.payload as Record<string, number | string>)[`${dataKey}-retirement-age`] ?? 0,
                  );
                  const phase = retirementAge > 0
                    ? `Retirement begins at age ${retirementAge}`
                    : withdrawal > 0
                      ? `Withdrawal: $${withdrawal.toLocaleString("en-US", { maximumFractionDigits: 0 })}/yr ${dollarDisplay === "future" ? "in that year's dollars" : "in today's dollars"}`
                      : "Contributing to retirement";
                  return withdrawal > 0 && retirementAge > 0
                    ? `${phase} · withdrawal: $${withdrawal.toLocaleString("en-US", { maximumFractionDigits: 0 })}/yr`
                    : phase;
                }}
              />
            }
          />
          {projectedScenarios.map((s) => (
            <Line
              key={s.id}
              type="monotone"
              dataKey={s.id}
              name={s.name}
              stroke={s.color}
              strokeWidth={activeIds.includes(s.id) ? 2.25 : 1}
              strokeOpacity={activeIds.includes(s.id) ? 1 : 0.25}
              dot={({ cx, cy, payload }) => {
                if (!activeIds.includes(s.id) || payload.year !== s.retirementYear) {
                  return <circle key={`${s.id}-${payload.year}`} cx={cx} cy={cy} r={0} fill="transparent" stroke="none" />;
                }
                return (
                  <circle
                    key={`${s.id}-${payload.year}`}
                    cx={cx}
                    cy={cy}
                    r={5}
                    fill="var(--card)"
                    stroke={s.color}
                    strokeWidth={2.5}
                  />
                );
              }}
              activeDot={{ r: 3, strokeWidth: 0 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
