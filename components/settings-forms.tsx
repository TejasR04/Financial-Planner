"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, ArchiveRestore, Check, Trash2 } from "lucide-react";
import { Panel, PanelHeader } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api, ApiArchivedAccount, ApiError, ApiIncomeSource, ApiDisconnectedDataSummary } from "@/lib/api-client";
import { useAccountsData, useDataRefresh, useInstitutionsData, useUserAccount } from "@/lib/data-provider";

const sections = [
  { id: "profile", label: "Profile" },
  { id: "planning", label: "Planning" },
  { id: "institutions", label: "Institutions" },
  { id: "archived", label: "Archived accounts" },
  { id: "notifications", label: "Notifications" },
];

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-1 gap-2 py-3.5 sm:grid-cols-[220px_1fr] sm:items-center sm:gap-4">
      <div>
        <p className="text-[13px] font-medium text-foreground">{label}</p>
        {hint ? (
          <p className="mt-0.5 text-[11px] text-muted-foreground">{hint}</p>
        ) : null}
      </div>
      <div>{children}</div>
    </div>
  );
}

const inputClass =
  "h-8 w-full rounded-md border border-border bg-background px-2.5 text-[13px] text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-ring focus:ring-3 focus:ring-ring/20 disabled:cursor-not-allowed disabled:opacity-60";

function Toggle({
  on,
  onChange,
  disabled = false,
}: {
  on: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        on ? "bg-primary" : "bg-muted",
      )}
    >
      <span
        className={cn(
          "inline-block size-4 rounded-full bg-background shadow-sm transition-transform",
          on ? "translate-x-4" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

export function SettingsForms() {
  const [tab, setTab] = useState("profile");
  const userAccount = useUserAccount();
  const accounts = useAccountsData();
  const institutions = useInstitutionsData();
  const refresh = useDataRefresh();
  const router = useRouter();
  const [mutationError, setMutationError] = useState<string | null>(null);

  // --- Profile tab ---------------------------------------------------
  const [fullName, setFullName] = useState("");
  const [dob, setDob] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);

  useEffect(() => {
    if (!userAccount) return;
    setFullName(userAccount.fullName);
    setDob(userAccount.dateOfBirth ?? "");
  }, [userAccount]);

  async function saveProfile() {
    setProfileSaving(true);
    setProfileSaved(false);
    setMutationError(null);
    try {
      await api.users.updateMe({
        full_name: fullName,
        base_currency: "USD",
        date_of_birth: dob || undefined,
      });
      refresh();
      setProfileSaved(true);
    } catch (error) {
      setMutationError(error instanceof ApiError ? error.message : "Couldn't save your profile.");
    } finally {
      setProfileSaving(false);
    }
  }

  // --- Planning tab ----------------------------------------------------
  const [retirementAge, setRetirementAge] = useState(65);
  const [equityAllocation, setEquityAllocation] = useState(60);
  const [withdrawalRate, setWithdrawalRate] = useState(4);
  const [includeSS, setIncludeSS] = useState(true);
  const [targetSavingsRate, setTargetSavingsRate] = useState("");
  const [cashReserveTarget, setCashReserveTarget] = useState("");
  const [incomeSources, setIncomeSources] = useState<ApiIncomeSource[]>([]);
  const [incomeName, setIncomeName] = useState("");
  const [incomeAmount, setIncomeAmount] = useState("");
  const [planningSaving, setPlanningSaving] = useState(false);
  const [planningSaved, setPlanningSaved] = useState(false);

  useEffect(() => {
    if (!userAccount) return;
    setRetirementAge(userAccount.targetRetirementAge);
    setEquityAllocation(Math.round(userAccount.targetEquityAllocation * 100));
    setWithdrawalRate(Math.round(userAccount.defaultWithdrawalRate * 1000) / 10);
    setIncludeSS(userAccount.includeSocialSecurity);
    setTargetSavingsRate(userAccount.targetSavingsRate == null ? "" : String(userAccount.targetSavingsRate * 100));
    setCashReserveTarget(userAccount.cashReserveTarget == null ? "" : String(userAccount.cashReserveTarget));
  }, [userAccount]);

  useEffect(() => { api.incomeSources.list().then(setIncomeSources).catch(() => setIncomeSources([])); }, []);

  async function savePlanning() {
    setPlanningSaving(true);
    setPlanningSaved(false);
    setMutationError(null);
    try {
      await api.users.updatePlanningProfile({
        target_retirement_age: retirementAge,
        target_equity_allocation: String(equityAllocation / 100),
        default_withdrawal_rate: String(withdrawalRate / 100),
        include_social_security: includeSS,
        target_savings_rate: targetSavingsRate === "" ? null : String(Number(targetSavingsRate) / 100),
        cash_reserve_target: cashReserveTarget === "" ? null : cashReserveTarget,
      });
      refresh();
      setPlanningSaved(true);
    } catch (error) {
      setMutationError(error instanceof ApiError ? error.message : "Couldn't save planning settings.");
    } finally {
      setPlanningSaving(false);
    }
  }

  async function removeIncomeSource(source: ApiIncomeSource) {
    setMutationError(null);
    try {
      await api.incomeSources.delete(source.id);
      setIncomeSources((rows) => rows.filter((row) => row.id !== source.id));
    } catch (error) {
      setMutationError(error instanceof ApiError ? error.message : "Couldn't remove that income source.");
    }
  }

  async function addIncomeSource() {
    setMutationError(null);
    try {
      const source = await api.incomeSources.create({
        name: incomeName,
        annual_amount: incomeAmount,
        growth_rate: "0.03",
      });
      setIncomeSources((rows) => [...rows, source]);
      setIncomeName("");
      setIncomeAmount("");
    } catch (error) {
      setMutationError(error instanceof ApiError ? error.message : "Couldn't add that income source.");
    }
  }

  // --- Archived accounts tab -------------------------------------------
  const [archivedAccounts, setArchivedAccounts] = useState<ApiArchivedAccount[]>([]);
  const [archivedLoading, setArchivedLoading] = useState(false);
  const [archivedError, setArchivedError] = useState<string | null>(null);
  const [archivedActionId, setArchivedActionId] = useState<string | null>(null);
  const [disconnectedData, setDisconnectedData] = useState<ApiDisconnectedDataSummary | null>(null);
  const [disconnectedDataError, setDisconnectedDataError] = useState<string | null>(null);
  const [permanentDeleteOpen, setPermanentDeleteOpen] = useState(false);
  const [permanentDeletePhrase, setPermanentDeletePhrase] = useState("");
  const [permanentDeleting, setPermanentDeleting] = useState(false);
  const [permanentDeleteFeedback, setPermanentDeleteFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (tab !== "archived") return;

    let cancelled = false;
    setArchivedLoading(true);
    setArchivedError(null);
    setDisconnectedDataError(null);
    setPermanentDeleteFeedback(null);

    void api.accounts.archived()
      .then((rows) => {
        if (!cancelled) setArchivedAccounts(rows);
      })
      .catch((error) => {
        if (!cancelled) {
          setArchivedError(error instanceof ApiError ? error.message : "Couldn't load archived accounts.");
        }
      })
      .finally(() => {
        if (!cancelled) setArchivedLoading(false);
      });

    // This endpoint intentionally covers only disconnected provider imports.
    // Manual archived accounts remain recoverable but are not eligible for
    // the irreversible data purge.
    void api.accounts.disconnectedImportedDataSummary()
      .then((summary) => {
        if (!cancelled) setDisconnectedData(summary);
      })
      .catch((error) => {
        if (!cancelled) {
          setDisconnectedDataError(error instanceof ApiError ? error.message : "Permanent deletion is unavailable right now.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [tab]);

  async function restoreArchivedAccount(account: ApiArchivedAccount) {
    setArchivedActionId(account.id);
    setArchivedError(null);
    try {
      await api.accounts.restore(account.id);
      setArchivedAccounts((rows) => rows.filter((row) => row.id !== account.id));
      setDisconnectedData((summary) => {
        if (!summary || !isDisconnectedImportedAccount(account)) return summary;
        return { ...summary, account_count: Math.max(0, summary.account_count - 1) };
      });
      refresh();
    } catch (error) {
      setArchivedError(error instanceof ApiError ? error.message : `Couldn't restore ${account.name}.`);
    } finally {
      setArchivedActionId(null);
    }
  }

  async function permanentlyDeleteDisconnectedData() {
    if (permanentDeletePhrase !== "DELETE") return;
    setPermanentDeleting(true);
    setDisconnectedDataError(null);
    setPermanentDeleteFeedback(null);
    try {
      const result = await api.accounts.permanentlyDeleteDisconnectedImportedData();
      setPermanentDeleteOpen(false);
      setPermanentDeletePhrase("");
      setDisconnectedData({ account_count: 0, transaction_count: 0 });
      setPermanentDeleteFeedback(
        `Permanently deleted ${result.account_count} archived account${result.account_count === 1 ? "" : "s"} and ${result.transaction_count} transaction${result.transaction_count === 1 ? "" : "s"}.`,
      );
      // The purge may remove several archived rows, and only the backend
      // knows which rows were imported. Reload instead of guessing locally.
      const rows = await api.accounts.archived();
      setArchivedAccounts(rows);
      refresh();
    } catch (error) {
      setDisconnectedDataError(error instanceof ApiError ? error.message : "Couldn't permanently delete the disconnected data.");
    } finally {
      setPermanentDeleting(false);
    }
  }

  const manualCount = accounts.filter((account) => !account.institutionId).length;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[180px_1fr]">
      {/* Section nav */}
      <nav className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
        {sections.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setTab(s.id)}
            className={cn(
              "whitespace-nowrap rounded-md px-2.5 py-1.5 text-left text-[13px] font-medium transition-colors",
              tab === s.id
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
            )}
          >
            {s.label}
          </button>
        ))}
      </nav>

      <div className="min-w-0">
        {mutationError && (
          <p role="alert" className="mb-4 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            {mutationError}
          </p>
        )}
        {tab === "profile" && (
          <Panel>
            <PanelHeader
              title="Profile"
              description="Your account identity and locale"
            />
            <div className="divide-y divide-border px-4">
              <Field label="Full name">
                <input
                  className={inputClass}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </Field>
              <Field label="Email" hint="Contact support to change your email">
                <input
                  className={inputClass}
                  type="email"
                  value={userAccount?.email ?? ""}
                  disabled
                />
              </Field>
              <Field label="Base currency">
                <input
                  className={inputClass}
                  value="USD — US Dollar"
                  disabled
                />
              </Field>
              <Field label="Date of birth" hint="Drives retirement horizon">
                <input
                  className={inputClass}
                  type="date"
                  value={dob}
                  onChange={(e) => setDob(e.target.value)}
                />
              </Field>
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-border p-3">
              {profileSaved && (
                <span className="text-[12px] text-positive">Saved</span>
              )}
              <Button size="sm" onClick={saveProfile} disabled={profileSaving}>
                <Check />
                {profileSaving ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </Panel>
        )}

        {tab === "planning" && (
          <Panel>
            <PanelHeader
              title="Planning assumptions"
              description="Defaults applied to new projections"
            />
            <div className="divide-y divide-border px-4">
              <Field label="Target retirement age">
                <input
                  className={inputClass}
                  type="number"
                  value={retirementAge}
                  onChange={(e) => setRetirementAge(Number(e.target.value))}
                />
              </Field>
              <Field
                label="Target equity allocation"
                hint="Used for drift alerts (%)"
              >
                <input
                  className={inputClass}
                  type="number"
                  value={equityAllocation}
                  onChange={(e) => setEquityAllocation(Number(e.target.value))}
                />
              </Field>
              <Field label="Default withdrawal rate" hint="%">
                <input
                  className={inputClass}
                  type="number"
                  step="0.1"
                  value={withdrawalRate}
                  onChange={(e) => setWithdrawalRate(Number(e.target.value))}
                />
              </Field>
              <Field
                label="Include Social Security"
                hint="Saved for future planning; current projections do not include benefits"
              >
                <Toggle on={includeSS} onChange={setIncludeSS} />
              </Field>
              <Field label="Target savings rate" hint="Required for the savings-discipline health score (%)">
                <input className={inputClass} type="number" min="0" max="100" step="0.1" value={targetSavingsRate} onChange={(e) => setTargetSavingsRate(e.target.value)} placeholder="Not configured" />
              </Field>
              <Field label="Cash reserve target" hint="Your chosen emergency/liquidity reserve in dollars">
                <input className={inputClass} type="number" min="0" step="100" value={cashReserveTarget} onChange={(e) => setCashReserveTarget(e.target.value)} placeholder="Not configured" />
              </Field>
              <Field label="Income sources" hint="Planning inputs only; never added to historical transaction income">
                <div className="space-y-2">
                  {incomeSources.map((source) => <div key={source.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-[12px]"><span>{source.name} · ${Number(source.annual_amount).toLocaleString()}/yr</span><Button variant="outline" size="xs" onClick={() => void removeIncomeSource(source)}>Remove</Button></div>)}
                  <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-2">
                    <input className={inputClass} value={incomeName} onChange={(e) => setIncomeName(e.target.value)} placeholder="Salary, pension…" />
                    <input className={inputClass} type="number" min="0" value={incomeAmount} onChange={(e) => setIncomeAmount(e.target.value)} placeholder="Annual amount" />
                    <Button variant="outline" size="sm" disabled={!incomeName || !incomeAmount} onClick={() => void addIncomeSource()}>Add</Button>
                  </div>
                </div>
              </Field>
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-border p-3">
              {planningSaved && (
                <span className="text-[12px] text-positive">Saved</span>
              )}
              <Button size="sm" onClick={savePlanning} disabled={planningSaving}>
                <Check />
                {planningSaving ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </Panel>
        )}

        {tab === "institutions" && (
          <Panel>
            <PanelHeader
              title="Connected institutions"
              description="Manage each distinct linked U.S. institution"
            />
            {institutions.length === 0 ? (
              <p className="px-4 py-6 text-center text-[13px] text-muted-foreground">
                No institutions linked yet. {manualCount ? `${manualCount} manual account${manualCount === 1 ? " is" : "s are"} managed from Accounts.` : ""}
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {institutions.map((institution) => {
                  const ok = institution.status === "healthy";
                  return (
                    <li
                      key={institution.id}
                      className="flex items-center justify-between gap-3 px-4 py-3"
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="flex size-7 items-center justify-center rounded-md border border-border bg-muted/50 font-mono text-[11px] font-semibold text-muted-foreground">
                          {institution.name.slice(0, 2).toUpperCase()}
                        </span>
                        <div>
                          <p className="text-[13px] font-medium text-foreground">
                            {institution.name}
                          </p>
                          <p className="text-[11px] text-muted-foreground">
                            {institution.accountCount} account{institution.accountCount !== 1 ? "s" : ""}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span
                          className={cn(
                            "flex items-center gap-1.5 text-[11px] font-medium",
                            ok ? "text-positive" : "text-warning",
                          )}
                        >
                          <span
                            className={cn(
                              "size-1.5 rounded-full",
                              ok ? "bg-positive" : "bg-warning",
                            )}
                          />
                          {ok ? "Healthy" : institution.status === "error" ? "Sync failed" : "Action required"}
                        </span>
                        <Button variant="outline" size="xs" onClick={() => router.push(`/accounts?institution=${institution.id}`)}>
                          Manage
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>
        )}

        {tab === "archived" && (
          <div className="space-y-4">
            <Panel>
              <PanelHeader
                title="Archived accounts"
                description="Hidden from your plan, with their historical activity preserved"
              />
              {archivedError && (
                <p role="alert" className="border-b border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                  {archivedError}
                </p>
              )}
              {archivedLoading ? (
                <p className="px-4 py-8 text-center text-[13px] text-muted-foreground">Loading archived accounts…</p>
              ) : archivedAccounts.length === 0 ? (
                <div className="px-4 py-8 text-center">
                  <ArchiveRestore className="mx-auto size-5 text-muted-foreground" />
                  <p className="mt-2 text-[13px] text-muted-foreground">No archived accounts.</p>
                  <p className="mt-1 text-[11px] text-muted-foreground">Accounts you archive or disconnect will appear here for recovery.</p>
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {archivedAccounts.map((account) => {
                    const linked = isLinkedAccount(account);
                    const detachedImported = isDisconnectedImportedAccount(account);
                    return (
                      <li key={account.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                        <div className="min-w-0">
                          <p className="truncate text-[13px] font-medium text-foreground">
                            {account.name}
                            {account.mask ? <span className="ml-1.5 font-mono text-[11px] text-muted-foreground">••{account.mask}</span> : null}
                          </p>
                          <p className="mt-0.5 text-[11px] text-muted-foreground">
                            {linked ? (account.institution ?? "Linked institution") : detachedImported ? "Disconnected provider" : "Manual account"} · {account.type[0].toUpperCase() + account.type.slice(1)} · Archived {formatArchivedDate(account.archived_at)}
                          </p>
                        </div>
                        <Button
                          variant="outline"
                          size="xs"
                          onClick={() => void restoreArchivedAccount(account)}
                          disabled={archivedActionId !== null || permanentDeleting || detachedImported}
                          title={detachedImported ? "Reconnect the provider before restoring this account." : undefined}
                        >
                          <ArchiveRestore />
                          {detachedImported ? "Reconnect required" : archivedActionId === account.id ? "Restoring…" : "Restore"}
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Panel>

            {disconnectedDataError && (
              <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-[12px] text-destructive">
                {disconnectedDataError}
              </p>
            )}
            {permanentDeleteFeedback && (
              <p role="status" className="rounded-md border border-positive/30 bg-positive/5 px-3 py-2 text-[12px] text-positive">
                {permanentDeleteFeedback}
              </p>
            )}

            {disconnectedData && (
              <Panel>
                <PanelHeader
                  title="Permanently delete imported data"
                  description="Available only for archived accounts disconnected from a provider"
                />
                <div className="space-y-3 px-4 py-4">
                  {disconnectedData.account_count === 0 ? (
                    <p className="text-[12px] text-muted-foreground">No disconnected imported account data is waiting to be deleted.</p>
                  ) : (
                    <>
                      <p className="text-[12px] leading-5 text-muted-foreground">
                        This will permanently remove <span className="font-medium text-foreground">{disconnectedData.account_count} account{disconnectedData.account_count === 1 ? "" : "s"}</span> and <span className="font-medium text-foreground">{disconnectedData.transaction_count} transaction{disconnectedData.transaction_count === 1 ? "" : "s"}</span> from Meridian. Manual archived accounts are not affected. This cannot be undone.
                      </p>
                      {permanentDeleteOpen ? (
                        <div className="space-y-3 rounded-md border border-destructive/30 bg-destructive/5 p-3">
                          <div className="flex gap-2">
                            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
                            <p className="text-[12px] leading-5 text-destructive">This permanently destroys imported financial history. Type <span className="font-mono font-semibold">DELETE</span> to continue.</p>
                          </div>
                          <label className="block text-[11px] font-medium text-foreground" htmlFor="permanent-delete-confirmation">Confirmation</label>
                          <input
                            id="permanent-delete-confirmation"
                            className={inputClass}
                            value={permanentDeletePhrase}
                            onChange={(event) => setPermanentDeletePhrase(event.target.value)}
                            placeholder="Type DELETE"
                            autoComplete="off"
                            spellCheck={false}
                          />
                          <div className="flex justify-end gap-2">
                            <Button variant="ghost" size="sm" onClick={() => { setPermanentDeleteOpen(false); setPermanentDeletePhrase(""); }} disabled={permanentDeleting}>Cancel</Button>
                            <Button variant="destructive" size="sm" onClick={() => void permanentlyDeleteDisconnectedData()} disabled={permanentDeletePhrase !== "DELETE" || permanentDeleting}>
                              <Trash2 />
                              {permanentDeleting ? "Deleting…" : "Permanently delete data"}
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <Button variant="destructive" size="sm" onClick={() => setPermanentDeleteOpen(true)} disabled={permanentDeleting}>
                          <Trash2 />
                          Permanently delete data
                        </Button>
                      )}
                    </>
                  )}
                </div>
              </Panel>
            )}
          </div>
        )}

        {tab === "notifications" && (
          <Panel>
            <PanelHeader
              title="Notifications"
              description="Notification delivery is coming soon"
            />
            <div className="divide-y divide-border px-4">
              {[
                {
                  label: "Weekly portfolio digest",
                  hint: "Every Monday at 8:00 AM",
                },
                {
                  label: "Allocation drift alerts",
                  hint: "When drift exceeds 5%",
                },
                {
                  label: "Large transaction alerts",
                  hint: "Transactions over $2,500",
                },
                {
                  label: "New AI recommendations",
                  hint: "When analysis surfaces opportunities",
                },
                {
                  label: "Bill & contribution reminders",
                  hint: "Two days before due dates",
                },
              ].map((n) => (
                <NotificationToggleField key={n.label} label={n.label} hint={n.hint} />
              ))}
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}

function formatArchivedDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "recently";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function isLinkedAccount(account: ApiArchivedAccount) {
  return Boolean(account.institution_id || account.institution);
}

function isDisconnectedImportedAccount(account: ApiArchivedAccount) {
  // A detached Plaid row can retain the connected status after the institution
  // relationship is removed. It must be reconnected before it can be restored;
  // the permanent purge endpoint is the supported cleanup path for this row.
  return !isLinkedAccount(account) && account.status === "connected";
}

// Delivery is not implemented yet, so the controls stay visibly unavailable
// instead of storing preferences that cannot produce notifications.
function NotificationToggleField({ label, hint }: { label: string; hint: string }) {
  return (
    <Field label={label} hint={`${hint} · Coming soon`}>
      <div className="flex sm:justify-start">
        <Toggle on={false} onChange={() => undefined} disabled />
      </div>
    </Field>
  );
}
