"use client";

import { Check } from "lucide-react";
import { type Milestone } from "@/lib/data";
import { useMilestones } from "@/lib/data-provider";
import { cn } from "@/lib/utils";

const dot: Record<Milestone["status"], string> = {
  done: "border-positive bg-positive text-positive-foreground",
  active:
    "border-primary bg-primary text-primary-foreground ring-4 ring-primary/15",
  upcoming: "border-border bg-card text-muted-foreground",
};

export function Timeline() {
  const milestones = useMilestones();
  return (
    <ol className="relative px-4 py-4">
      {milestones.map((m, i) => {
        const last = i === milestones.length - 1;
        return (
          <li key={m.id} className="relative flex gap-3.5 pb-5 last:pb-0">
            {!last && (
              <span
                className={cn(
                  "absolute left-[11px] top-6 h-full w-px",
                  m.status === "done" ? "bg-positive/40" : "bg-border",
                )}
              />
            )}
            <span
              className={cn(
                "relative z-10 mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold",
                dot[m.status],
              )}
            >
              {m.status === "done" ? <Check className="size-3.5" /> : (m.age ?? "—")}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className="text-[13px] font-medium text-foreground">
                  {m.title}
                </p>
                <span className="font-mono text-xs font-medium text-foreground tabular-nums">
                  {m.amount}
                </span>
              </div>
              <div className="mt-0.5 flex items-center gap-2">
                <span className="font-mono text-[11px] text-muted-foreground">
                  {m.year}
                </span>
                {m.detail && (
                  <>
                    <span className="text-muted-foreground/40">·</span>
                    <p className="truncate text-xs text-muted-foreground">
                      {m.detail}
                    </p>
                  </>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
