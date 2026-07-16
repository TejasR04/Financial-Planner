"use client";

import { ArrowUpRight, ArrowDownRight } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import type { Kpi } from "@/lib/data";
import { cn } from "@/lib/utils";

export function KpiCard({ kpi }: { kpi: Kpi }) {
  const up = kpi.trend === "up";
  const data = kpi.spark.map((v, i) => ({ i, v }));
  const gradId = `spark-${kpi.id}`;

  return (
    <div className="group relative flex flex-col justify-between rounded-lg border border-border bg-card p-4 transition-colors hover:border-foreground/20">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">
            {kpi.label}
          </p>
          <p className="mt-1.5 text-2xl font-semibold tracking-tight text-foreground tabular-nums">
            {kpi.value}
          </p>
        </div>
        <span
          className={cn(
            "inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[11px] font-medium tabular-nums",
            up
              ? "bg-positive/10 text-positive"
              : "bg-destructive/10 text-destructive",
          )}
        >
          {up ? (
            <ArrowUpRight className="size-3" />
          ) : (
            <ArrowDownRight className="size-3" />
          )}
          {Math.abs(kpi.delta).toFixed(1)}%
        </span>
      </div>

      <div className="mt-3 flex items-end justify-between gap-3">
        <p className="text-[11px] text-muted-foreground">{kpi.deltaLabel}</p>
        <div className="h-8 w-24">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 2, bottom: 2, left: 0, right: 0 }}
            >
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor={up ? "var(--positive)" : "var(--destructive)"}
                    stopOpacity={0.25}
                  />
                  <stop
                    offset="100%"
                    stopColor={up ? "var(--positive)" : "var(--destructive)"}
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="v"
                stroke={up ? "var(--positive)" : "var(--destructive)"}
                strokeWidth={1.5}
                fill={`url(#${gradId})`}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
