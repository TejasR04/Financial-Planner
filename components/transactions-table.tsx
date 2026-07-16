"use client";

import { transactions, formatCurrency } from "@/lib/data";
import { cn } from "@/lib/utils";

export function TransactionsTable() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-border text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            <th className="px-4 py-2 font-medium">Date</th>
            <th className="px-4 py-2 font-medium">Merchant</th>
            <th className="px-4 py-2 font-medium">Category</th>
            <th className="hidden px-4 py-2 font-medium lg:table-cell">
              Account
            </th>
            <th className="px-4 py-2 text-right font-medium">Amount</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((t) => (
            <tr
              key={t.id}
              className="border-b border-border/60 transition-colors last:border-0 hover:bg-muted/40"
            >
              <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-muted-foreground tabular-nums">
                {t.date}
              </td>
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-foreground">
                    {t.merchant}
                  </span>
                  {t.status === "pending" && (
                    <span className="rounded border border-warning/30 bg-warning/10 px-1 py-px text-[10px] font-medium text-warning">
                      pending
                    </span>
                  )}
                </div>
              </td>
              <td className="px-4 py-2.5 text-muted-foreground">
                {t.category}
              </td>
              <td className="hidden px-4 py-2.5 text-muted-foreground lg:table-cell">
                {t.account}
              </td>
              <td
                className={cn(
                  "whitespace-nowrap px-4 py-2.5 text-right font-mono font-medium tabular-nums",
                  t.amount >= 0 ? "text-positive" : "text-foreground",
                )}
              >
                {formatCurrency(t.amount, { sign: true })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
