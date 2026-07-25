"use client";

import { useEffect, useState } from "react";
import { Info, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { PageContainer, PageHeader } from "@/components/page-container";
import { ScenarioCompare } from "@/components/scenario-compare";
import { ProjectionAssumptions } from "@/components/projection-assumptions";
import { SensitivityAnalysis } from "@/components/sensitivity-analysis";
import { NewScenarioDialog } from "@/components/new-scenario-dialog";
import { Panel, PanelHeader } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, ApiError } from "@/lib/api-client";
import { formatCurrency, type Scenario } from "@/lib/data";
import { useCurrentAge, useCurrentRetirementBalance, useDataRefresh, useScenariosData } from "@/lib/data-provider";

export default function ProjectionsPage() {
  const scenarios = useScenariosData();
  const refresh = useDataRefresh();
  const currentAge = useCurrentAge();
  const currentRetirementBalance = useCurrentRetirementBalance();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingScenario, setEditingScenario] = useState<Scenario | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [pendingEditId, setPendingEditId] = useState<string | null>(null);
  const [runningScenarioId, setRunningScenarioId] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const best =
    scenarios.length > 0
      ? scenarios.reduce((a, b) => (b.successRate > a.successRate ? b : a))
      : null;

  // After "Duplicate & edit" creates a copy, open the edit dialog on it as
  // soon as the refreshed scenario list actually contains it.
  useEffect(() => {
    if (!pendingEditId) return;
    const found = scenarios.find((s) => s.id === pendingEditId);
    if (found) {
      setEditingScenario(found);
      setDialogOpen(true);
      setPendingEditId(null);
    }
  }, [scenarios, pendingEditId]);

  const openCreate = () => {
    setEditingScenario(null);
    setDialogOpen(true);
  };
  const openEdit = (s: Scenario) => {
    setEditingScenario(s);
    setDialogOpen(true);
  };
  const confirmDelete = async (id: string) => {
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.scenarios.delete(id);
      refresh();
      setPendingDeleteId(null);
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "Couldn't delete that scenario.");
    } finally {
      setDeleting(false);
    }
  };
  const runScenario = async (scenarioId: string) => {
    if (currentAge == null || currentRetirementBalance == null) return;
    setRunningScenarioId(scenarioId);
    setRunError(null);
    try {
      await api.scenarios.run(scenarioId, {
        current_age: currentAge,
        current_retirement_balance: String(currentRetirementBalance),
        include_monte_carlo: true,
        monte_carlo_trials: 1000,
      });
      refresh();
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : "Couldn't run this scenario.");
    } finally {
      setRunningScenarioId(null);
    }
  };

  return (
    <PageContainer>
      <NewScenarioDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        scenario={editingScenario}
      />
      <PageHeader
        title="Projections"
        description="Monte Carlo modeling across savings, allocation, and retirement scenarios"
        actions={
          <>
            <Button variant="outline" size="sm">
              <Sparkles />
              Optimize
            </Button>
            <Button size="sm" onClick={openCreate}>
              <Plus />
              New scenario
            </Button>
          </>
        }
      />

      {/* Scenario summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {scenarios.map((s) => (
          <div
            key={s.id}
            className="flex flex-col rounded-lg border border-border bg-card p-4"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className="size-2.5 rounded-[3px]"
                  style={{ background: s.color }}
                />
                <span className="text-[13px] font-semibold text-foreground">
                  {s.name}
                </span>
                {s.desiredMonthlyIncomeToday != null && (
                  <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                    ${s.desiredMonthlyIncomeToday.toLocaleString()}/mo target
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                {s.id === best?.id && (
                  <Badge variant="positive">Recommended</Badge>
                )}
                <button
                  type="button"
                  onClick={() => openEdit(s)}
                  className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                  aria-label={`Edit ${s.name}`}
                >
                  <Pencil className="size-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setDeleteError(null);
                    setPendingDeleteId(s.id);
                  }}
                  className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                  aria-label={`Delete ${s.name}`}
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            </div>
            {pendingDeleteId === s.id && (
              <div className="mt-2 flex items-center justify-between gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-2.5 py-1.5">
                <span className="text-[12px] text-destructive">Delete this scenario?</span>
                <div className="flex gap-1.5">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-6 px-2 text-[11px]"
                    onClick={() => setPendingDeleteId(null)}
                    disabled={deleting}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    className="h-6 bg-destructive px-2 text-[11px] text-destructive-foreground hover:bg-destructive/90"
                    onClick={() => confirmDelete(s.id)}
                    disabled={deleting}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            )}
            {deleteError && pendingDeleteId === s.id && (
              <p className="mt-1 text-[11px] text-destructive">{deleteError}</p>
            )}
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground text-pretty">
              {s.description}
            </p>
            <div className="mt-3 flex items-end justify-between border-t border-border pt-3">
              <div>
                <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  Retirement balance at {s.retirementAge}
                </p>
                <p className="font-mono text-lg font-semibold text-foreground tabular-nums">
                  {formatCurrency(s.netWorthAt65, { compact: true })}
                </p>
              </div>
              <div className="text-right">
                <p className="flex items-center justify-end gap-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                  Success
                  <Info
                    className="size-3 shrink-0 text-muted-foreground/70"
                    aria-label="Of 1,000 simulated trials with randomized annual returns, the percentage where retirement savings lasted through age 95 without running out. Contributions stop at retirement age; the plan's sustainable withdrawal (a % of that scenario's own balance) is taken out each year of retirement. Because withdrawal scales with balance, a bigger balance alone doesn't raise this number much."
                  >
                    <title>
                      Of 1,000 simulated trials with randomized annual returns, the percentage
                      where retirement savings lasted through age 95 without running out.
                      Contributions stop at retirement age; the plan&apos;s sustainable withdrawal
                      (a % of that scenario&apos;s own balance) is taken out each year of
                      retirement. Because withdrawal scales with balance, a bigger balance alone
                      doesn&apos;t raise this number much — it mainly reflects withdrawal rate,
                      expected return, and volatility.
                    </title>
                  </Info>
                </p>
                <p className="font-mono text-lg font-semibold text-primary tabular-nums">
                  {s.successRate}%
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="mt-3 w-full"
              onClick={() => runScenario(s.id)}
              disabled={runningScenarioId !== null || currentAge == null || currentRetirementBalance == null}
            >
              <Sparkles />
              {runningScenarioId === s.id ? "Running simulation…" : "Run analysis"}
            </Button>
            {runError && (
              <p className="mt-1.5 text-[11px] text-destructive">{runError}</p>
            )}
          </div>
        ))}
      </div>

      {/* Comparison */}
      <div className="mt-4">
        <ScenarioCompare onDuplicated={setPendingEditId} />
      </div>

      {/* Assumptions + notes */}
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="xl:col-span-1">
          <ProjectionAssumptions />
        </div>

        <SensitivityAnalysis scenarios={scenarios} />
      </div>
    </PageContainer>
  );
}
