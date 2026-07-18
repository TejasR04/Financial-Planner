"use client";

import {
  Landmark,
  LineChart,
  PiggyBank,
  CreditCard,
  Building2,
  CircleDollarSign,
  ArrowUpRight,
  ArrowDownRight,
  type LucideIcon,
} from "lucide-react";
import { type Account, formatCurrency, formatPercent } from "@/lib/data";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const typeIcon: Record<Account["type"], LucideIcon> = {
  Investment: LineChart,
  Depository: Landmark,
  Retirement: PiggyBank,
  Credit: CreditCard,
  Loan: CircleDollarSign,
  Property: Building2,
};

const statusBadge: Record<
  Account["status"],
  { label: string; variant: "positive" | "warning" | "outline" }
> = {
  connected: { label: "Connected", variant: "positive" },
  attention: { label: "Needs attention", variant: "warning" },
  manual: { label: "Manual", variant: "outline" },
};

export function AccountCard({ account }: { account: Account }) {
  const Icon = typeIcon[account.type];
  const negative = account.balance < 0;
  const badge = statusBadge[account.status];

  return (
    <div className="group flex flex-col rounded-lg border border-border bg-card p-4 transition-colors hover:border-foreground/20">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-md border border-border bg-muted/50 text-muted-foreground">
            <Icon className="size-4" />
          </span>
          <div>
            <p className="text-[13px] font-medium text-foreground">
              {account.name}
            </p>
            <p className="text-[11px] text-muted-foreground">
              {account.institution ? `${account.institution} · ` : ""}
              <span className="font-mono">••{account.mask}</span>
            </p>
          </div>
        </div>
        <Badge variant={badge.variant}>{badge.label}</Badge>
      </div>

      <div className="mt-3.5 flex items-end justify-between">
        <div>
          <p
            className={cn(
              "font-mono text-lg font-semibold tracking-tight tabular-nums",
              negative ? "text-foreground" : "text-foreground",
            )}
          >
            {formatCurrency(account.balance)}
          </p>
          <div className="mt-0.5 flex items-center gap-2 text-[11px]">
            {account.change != null && (
              <span
                className={cn(
                  "inline-flex items-center gap-0.5 font-medium tabular-nums",
                  account.change >= 0 ? "text-positive" : "text-destructive",
                )}
              >
                {account.change >= 0 ? (
                  <ArrowUpRight className="size-3" />
                ) : (
                  <ArrowDownRight className="size-3" />
                )}
                {formatPercent(Math.abs(account.change))}
              </span>
            )}
            <span className="text-muted-foreground">· {account.updated}</span>
          </div>
        </div>
        {account.apy != null && (
          <div className="text-right">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
              APY
            </p>
            <p className="font-mono text-sm font-medium text-foreground tabular-nums">
              {account.apy}%
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
