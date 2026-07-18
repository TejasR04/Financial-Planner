"use client";

import {
  Sparkles,
  Lightbulb,
  TriangleAlert,
  Info,
  ArrowRight,
} from "lucide-react";
import { type Insight } from "@/lib/data";
import { useInsightsData } from "@/lib/data-provider";
import { cn } from "@/lib/utils";

const config: Record<
  Insight["kind"],
  { icon: typeof Info; label: string; tint: string; bg: string }
> = {
  opportunity: {
    icon: Lightbulb,
    label: "Opportunity",
    tint: "text-positive",
    bg: "bg-positive/10",
  },
  alert: {
    icon: TriangleAlert,
    label: "Alert",
    tint: "text-warning",
    bg: "bg-warning/15",
  },
  observation: {
    icon: Info,
    label: "Observation",
    tint: "text-primary",
    bg: "bg-accent",
  },
};

export function AiInsights({ className }: { className?: string }) {
  const insights = useInsightsData();
  return (
    <div
      className={cn(
        "flex flex-col rounded-lg border border-border bg-card",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="flex size-5 items-center justify-center rounded-md bg-primary/10">
            <Sparkles className="size-3.5 text-primary" />
          </span>
          <h2 className="text-[13px] font-semibold tracking-tight text-foreground">
            AI Insights
          </h2>
        </div>
        <span className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground">
          <span className="size-1.5 animate-pulse rounded-full bg-positive" />
          Updated 4m ago
        </span>
      </div>

      <ul className="divide-y divide-border">
        {insights.map((insight) => {
          const c = config[insight.kind];
          const Icon = c.icon;
          return (
            <li key={insight.id} className="group flex gap-3 px-4 py-3">
              <span
                className={cn(
                  "mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md",
                  c.bg,
                )}
              >
                <Icon className={cn("size-3.5", c.tint)} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className={cn("text-[11px] font-semibold", c.tint)}>
                    {c.label}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {insight.meta}
                  </span>
                </div>
                <p className="mt-1 text-[13px] leading-relaxed text-foreground/90 text-pretty">
                  {insight.text}
                </p>
              </div>
            </li>
          );
        })}
      </ul>

      <button
        type="button"
        className="flex items-center justify-center gap-1.5 border-t border-border px-4 py-2.5 text-[12px] font-medium text-primary transition-colors hover:bg-accent/50"
      >
        View full analysis
        <ArrowRight className="size-3.5" />
      </button>
    </div>
  );
}
