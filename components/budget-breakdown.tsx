"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Panel, PanelHeader } from "./panel";
import type { ApiBudgetSummary } from "@/lib/api-client";
import { formatCurrency } from "@/lib/data";

const COLORS = ["#2563eb", "#0891b2", "#16a34a", "#ea580c", "#9333ea", "#e11d48", "#a16207", "#0f766e", "#4f46e5", "#be185d", "#64748b", "#65a30d"];

export function BudgetBreakdown({ summary, loading, onSelect }: { summary: ApiBudgetSummary | null; loading: boolean; onSelect: (id: string) => void }) {
  const rows = (summary?.categories ?? []).map((row, index) => ({ id: row.budget_category_id, name: row.name, spent: Number(row.spent) + Number(row.pending), color: COLORS[index % COLORS.length] })).sort((a, b) => b.spent - a.spent);
  const slices = rows.filter((row) => row.spent > 0);
  const net = rows.reduce((total, row) => total + row.spent, 0);
  return <Panel>
    <PanelHeader title="Category breakdown" description="Categorized spending · select a category to see transactions" />
    {loading ? <p className="flex min-h-64 items-center justify-center text-sm text-muted-foreground">Loading categories…</p> : <>
      <div className="grid flex-1 items-center gap-4 p-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <div className="relative h-52 min-w-0">
          {slices.length > 0 && <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={slices} dataKey="spent" nameKey="name" innerRadius="65%" outerRadius="90%" paddingAngle={1} isAnimationActive={false} onClick={(entry) => onSelect(entry.id)} cursor="pointer">{slices.map((row) => <Cell key={row.id} fill={row.color} />)}</Pie><Tooltip formatter={(value) => formatCurrency(Number(value))} /></PieChart></ResponsiveContainer>}
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center"><span className="text-xs text-muted-foreground">Net categorized</span><strong className="mt-1 text-lg tabular-nums">{formatCurrency(net)}</strong></div>
        </div>
        <div className="max-h-60 space-y-1 overflow-y-auto">
          {rows.filter((row) => row.spent !== 0).map((row) => <button key={row.id} onClick={() => onSelect(row.id)} className="flex w-full items-center gap-2 rounded px-1 py-1.5 text-left text-xs hover:bg-muted focus-visible:outline-ring"><span className="size-2 shrink-0 rounded-full" style={{ background: row.color }} /><span className="min-w-0 flex-1 truncate">{row.name}</span><span className="tabular-nums">{formatCurrency(row.spent)}</span></button>)}
          {!rows.some((row) => row.spent !== 0) && <p className="text-xs text-muted-foreground">No categorized spending for this month.</p>}
        </div>
      </div>
      {rows.some((row) => row.spent < 0) && <p className="px-4 pb-3 text-xs text-muted-foreground">Net credits are listed but omitted from the donut slices.</p>}
    </>}
  </Panel>;
}
