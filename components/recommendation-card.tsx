"use client";

import { useState } from "react";
import { Check, ArrowRight } from "lucide-react";
import { type Recommendation } from "@/lib/data";
import { api } from "@/lib/api-client";
import { useDataRefresh } from "@/lib/data-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const effortColor: Record<Recommendation["effort"], string> = {
  Low: "text-positive",
  Medium: "text-warning",
  High: "text-destructive",
};

export function RecommendationCard({ rec }: { rec: Recommendation }) {
  const refresh = useDataRefresh();
  const [pending, setPending] = useState<"applied" | "dismissed" | null>(null);

  async function handleAction(status: "applied" | "dismissed") {
    setPending(status);
    try {
      await api.recommendations.update(rec.id, status);
      refresh();
    } catch {
      setPending(null);
    }
  }

  return (
    <div className="flex flex-col rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Badge variant="primary">{rec.category}</Badge>
          <span className="text-[11px] text-muted-foreground">
            Effort:{" "}
            <span className={cn("font-medium", effortColor[rec.effort])}>
              {rec.effort}
            </span>
          </span>
        </div>
        <span className="whitespace-nowrap rounded-md bg-positive/10 px-2 py-0.5 font-mono text-[13px] font-semibold text-positive tabular-nums">
          {rec.impact}
        </span>
      </div>

      <h3 className="mt-3 text-[14px] font-semibold leading-snug tracking-tight text-foreground text-pretty">
        {rec.title}
      </h3>
      <p className="mt-1.5 flex-1 text-[13px] leading-relaxed text-muted-foreground text-pretty">
        {rec.body}
      </p>

      <div className="mt-4 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${Math.round(rec.confidence * 100)}%` }}
            />
          </div>
          <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
            {Math.round(rec.confidence * 100)}% confidence
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="xs"
            onClick={() => handleAction("dismissed")}
            disabled={pending !== null}
          >
            {pending === "dismissed" ? "Dismissing…" : "Dismiss"}
          </Button>
          <Button size="xs" onClick={() => handleAction("applied")} disabled={pending !== null}>
            <Check />
            {pending === "applied" ? "Applying…" : "Apply"}
          </Button>
        </div>
      </div>
    </div>
  );
}
