"use client";

import type { TooltipProps } from "recharts";

export function ChartTooltip({
  active,
  payload,
  label,
  formatter,
}: TooltipProps<number, string> & {
  formatter?: (value: number) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-md border border-border bg-popover px-2.5 py-2 text-xs shadow-lg shadow-foreground/5">
      {label ? (
        <p className="mb-1 font-medium text-foreground">{label}</p>
      ) : null}
      <div className="flex flex-col gap-1">
        {payload.map((entry, i) => (
          <div key={i} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <span
                className="size-2 rounded-[2px]"
                style={{ background: entry.color as string }}
              />
              {entry.name}
            </span>
            <span className="font-mono font-medium text-foreground tabular-nums">
              {formatter ? formatter(entry.value as number) : entry.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
