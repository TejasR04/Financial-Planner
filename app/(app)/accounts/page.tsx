"use client";

import { useCallback, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Pencil, Plus, RefreshCw, Unlink } from "lucide-react";
import { PageContainer, PageHeader } from "@/components/page-container";
import { Panel, PanelHeader } from "@/components/panel";
import { AccountCard } from "@/components/account-card";
import { ManualAccountDialog } from "@/components/manual-account-dialog";
import { Button } from "@/components/ui/button";
import { PlaidLinkButton } from "@/components/plaid-link-button";
import { formatCurrency, type Account, type Institution } from "@/lib/data";
import { ApiError, api } from "@/lib/api-client";
import { useAccountsData, useDataRefresh, useInstitutionsData } from "@/lib/data-provider";

type SyncFeedback = { tone: "success" | "error"; message: string } | null;

let activePlaidRefresh: ReturnType<typeof api.plaid.refresh> | null = null;

function requestPlaidRefresh() {
  if (activePlaidRefresh === null) {
    activePlaidRefresh = api.plaid.refresh().finally(() => {
      activePlaidRefresh = null;
    });
  }
  return activePlaidRefresh;
}

const isLiability = (account: Account) => account.type === "Credit" || account.type === "Loan";

function institutionStatusLabel(institution: Institution) {
  if (institution.status === "healthy") return "Healthy";
  if (institution.status === "action_required") return "Action required";
  return "Sync failed";
}

export default function AccountsPage() {
  const accounts = useAccountsData();
  const institutions = useInstitutionsData();
  const refreshData = useDataRefresh();
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedInstitutionId = searchParams.get("institution");
  const [syncing, setSyncing] = useState(false);
  const [syncFeedback, setSyncFeedback] = useState<SyncFeedback>(null);
  const [manualDialogOpen, setManualDialogOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);

  const visibleAccounts = selectedInstitutionId
    ? accounts.filter((account) => account.institutionId === selectedInstitutionId)
    : accounts;
  const assetAccounts = visibleAccounts.filter((account) => !isLiability(account));
  const liabilityAccounts = visibleAccounts.filter(isLiability);
  const assets = assetAccounts.reduce((sum, account) => sum + account.balance, 0);
  const liabilities = liabilityAccounts.reduce((sum, account) => sum + Math.max(0, -account.balance), 0);
  const net = visibleAccounts.reduce((sum, account) => sum + account.balance, 0);
  const linkedCount = visibleAccounts.filter((account) => account.institutionId).length;
  const manualCount = visibleAccounts.length - linkedCount;

  const syncAll = useCallback(async () => {
    setSyncing(true);
    setSyncFeedback(null);
    try {
      const result = await requestPlaidRefresh();
      refreshData();
      const failures = result.data.filter((institution) => institution.error);
      if (failures.length > 0) {
        setSyncFeedback({ tone: "error", message: `${failures.length} institution${failures.length === 1 ? "" : "s"} need attention. Open the institution section below to reconnect each one.` });
      } else if (result.data.length === 0) {
        setSyncFeedback({ tone: "success", message: "No linked institutions to sync. Add a manual account or link a U.S. institution." });
      } else {
        setSyncFeedback({ tone: "success", message: `Synced ${result.data.length} linked institution${result.data.length === 1 ? "" : "s"}.` });
      }
    } catch (error) {
      setSyncFeedback({ tone: "error", message: error instanceof ApiError ? error.message : "Couldn't sync your linked institutions. Try again." });
    } finally {
      setSyncing(false);
    }
  }, [refreshData]);

  const syncInstitution = async (institution: Institution) => {
    const account = accounts.find((item) => item.institutionId === institution.id);
    if (!account) return;
    setPendingActionId(institution.id);
    setSyncFeedback(null);
    try {
      const result = await api.accounts.sync(account.id);
      refreshData();
      setSyncFeedback(result.error ? { tone: "error", message: `${institution.name}: ${result.error}` } : { tone: "success", message: `${institution.name} synced successfully.` });
    } catch (error) {
      setSyncFeedback({ tone: "error", message: error instanceof ApiError ? error.message : `Couldn't sync ${institution.name}.` });
    } finally {
      setPendingActionId(null);
    }
  };

  const unlinkInstitution = async (institution: Institution) => {
    if (!window.confirm(`Unlink ${institution.name}? Its accounts will be archived and removed from your plan.`)) return;
    setPendingActionId(institution.id);
    try {
      await api.accounts.unlinkInstitution(institution.id);
      refreshData();
      if (selectedInstitutionId === institution.id) router.replace("/accounts");
      setSyncFeedback({ tone: "success", message: `${institution.name} was unlinked. Its previous accounts are archived.` });
    } catch (error) {
      setSyncFeedback({ tone: "error", message: error instanceof ApiError ? error.message : `Couldn't unlink ${institution.name}.` });
    } finally {
      setPendingActionId(null);
    }
  };

  const archiveManual = async (account: Account) => {
    if (!window.confirm(`Archive ${account.name}?`)) return;
    setPendingActionId(account.id);
    try {
      await api.accounts.delete(account.id);
      refreshData();
    } catch (error) {
      setSyncFeedback({ tone: "error", message: error instanceof ApiError ? error.message : `Couldn't archive ${account.name}.` });
    } finally {
      setPendingActionId(null);
    }
  };

  const cardActions = (account: Account) => account.institutionId ? (
    <Button variant="ghost" size="icon-xs" aria-label={`Sync ${account.name}`} onClick={() => { const institution = institutions.find((item) => item.id === account.institutionId); if (institution) void syncInstitution(institution); }} disabled={pendingActionId !== null}>
      <RefreshCw className={pendingActionId === account.institutionId ? "animate-spin" : undefined} />
    </Button>
  ) : (
    <div className="flex items-center">
      <Button variant="ghost" size="icon-xs" aria-label={`Edit ${account.name}`} onClick={() => { setEditingAccount(account); setManualDialogOpen(true); }}><Pencil /></Button>
      <Button variant="ghost" size="icon-xs" aria-label={`Archive ${account.name}`} onClick={() => void archiveManual(account)} disabled={pendingActionId === account.id}><Unlink /></Button>
    </div>
  );

  return (
    <PageContainer>
      <ManualAccountDialog open={manualDialogOpen} account={editingAccount} onClose={() => { setManualDialogOpen(false); setEditingAccount(null); }} />
      <PageHeader
        title="Accounts"
        description={`${visibleAccounts.length} account${visibleAccounts.length === 1 ? "" : "s"} · ${linkedCount} linked · ${manualCount} manual · USD`}
        actions={<><Button variant="outline" size="sm" onClick={() => void syncAll()} disabled={syncing}><RefreshCw className={syncing ? "animate-spin" : undefined} />{syncing ? "Syncing…" : "Sync all"}</Button><Button variant="outline" size="sm" onClick={() => { setEditingAccount(null); setManualDialogOpen(true); }}><Plus />Add manual</Button><PlaidLinkButton size="sm" /></>}
      />

      {selectedInstitutionId && <div className="mb-4 flex items-center justify-between rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground"><span>Showing one linked institution.</span><Button variant="ghost" size="xs" onClick={() => router.replace("/accounts")}>Show all accounts</Button></div>}
      {syncFeedback && <div role="status" className={`mb-4 rounded-md border px-3 py-2 text-xs ${syncFeedback.tone === "error" ? "border-destructive/30 bg-destructive/5 text-destructive" : "border-positive/30 bg-positive/5 text-positive"}`}>{syncFeedback.message}</div>}

      <div className="grid grid-cols-1 divide-y divide-border overflow-hidden rounded-lg border border-border bg-card sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        {[{ label: "Total assets", value: formatCurrency(assets), tint: "text-foreground" }, { label: "Total liabilities", value: formatCurrency(liabilities), tint: "text-destructive" }, { label: "Net worth", value: formatCurrency(net), tint: "text-primary" }].map((summary) => <div key={summary.label} className="px-5 py-4"><p className="text-xs font-medium text-muted-foreground">{summary.label}</p><p className={`mt-1.5 font-mono text-2xl font-semibold tracking-tight tabular-nums ${summary.tint}`}>{summary.value}</p></div>)}
      </div>

      <Panel className="mt-4">
        <PanelHeader title="Linked institutions" description="Sync, reconnect, or unlink each U.S. institution" />
        {institutions.length === 0 ? <p className="px-4 py-8 text-center text-sm text-muted-foreground">No institutions linked yet. Link a U.S. bank or add an account manually.</p> : <ul className="divide-y divide-border">{institutions.map((institution) => <li key={institution.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"><div><p className="text-sm font-medium text-foreground">{institution.name}</p><p className="mt-0.5 text-xs text-muted-foreground">{institution.accountCount} account{institution.accountCount === 1 ? "" : "s"} · {institution.lastSyncedAt ? `Synced ${new Date(institution.lastSyncedAt).toLocaleString()}` : "Not synced yet"}</p></div><div className="flex items-center gap-2"><span className={institution.status === "healthy" ? "text-xs font-medium text-positive" : "text-xs font-medium text-warning"}>{institutionStatusLabel(institution)}</span><Button variant="outline" size="xs" onClick={() => void syncInstitution(institution)} disabled={pendingActionId !== null}><RefreshCw className={pendingActionId === institution.id ? "animate-spin" : undefined} />Sync</Button>{institution.status !== "healthy" && <PlaidLinkButton label="Reconnect" institutionId={institution.id} size="xs" variant="outline" />}<Button variant="ghost" size="xs" onClick={() => void unlinkInstitution(institution)} disabled={pendingActionId !== null}><Unlink />Unlink</Button></div></li>)}</ul>}
      </Panel>

      <section className="mt-6"><div className="flex items-center justify-between"><h2 className="text-[13px] font-semibold tracking-tight text-foreground">Assets</h2><span className="font-mono text-xs text-muted-foreground tabular-nums">{assetAccounts.length} accounts · {formatCurrency(assets, { compact: true })}</span></div>{assetAccounts.length === 0 ? <p className="mt-3 rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">No asset accounts yet.</p> : <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">{assetAccounts.map((account) => <AccountCard key={account.id} account={account} actions={cardActions(account)} />)}</div>}</section>
      <section className="mt-6"><div className="flex items-center justify-between"><h2 className="text-[13px] font-semibold tracking-tight text-foreground">Liabilities</h2><span className="font-mono text-xs text-muted-foreground tabular-nums">{liabilityAccounts.length} accounts · {formatCurrency(liabilities, { compact: true })}</span></div>{liabilityAccounts.length === 0 ? <p className="mt-3 rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">No credit or loan accounts yet.</p> : <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">{liabilityAccounts.map((account) => <AccountCard key={account.id} account={account} actions={cardActions(account)} />)}</div>}</section>

      <Panel className="mt-6"><PanelHeader title="All positions" description="Complete active account ledger" />{visibleAccounts.length === 0 ? <p className="px-4 py-10 text-center text-sm text-muted-foreground">Link a U.S. institution or add a manual account to begin.</p> : <div className="overflow-x-auto"><table className="w-full border-collapse text-[13px]"><thead><tr className="border-b border-border text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground"><th className="px-4 py-2 font-medium">Account</th><th className="px-4 py-2 font-medium">Type</th><th className="hidden px-4 py-2 font-medium md:table-cell">Institution</th><th className="hidden px-4 py-2 font-medium lg:table-cell">Last sync</th><th className="px-4 py-2 text-right font-medium">Balance</th></tr></thead><tbody>{visibleAccounts.map((account) => <tr key={account.id} className="border-b border-border/60 last:border-0"><td className="px-4 py-2.5"><span className="font-medium text-foreground">{account.name}</span><span className="ml-1.5 font-mono text-[11px] text-muted-foreground">••{account.mask}</span></td><td className="px-4 py-2.5 text-muted-foreground">{account.type}</td><td className="hidden px-4 py-2.5 text-muted-foreground md:table-cell">{account.institution ?? "Manual"}</td><td className="hidden px-4 py-2.5 font-mono text-xs text-muted-foreground tabular-nums lg:table-cell">{account.updated}</td><td className="whitespace-nowrap px-4 py-2.5 text-right font-mono font-medium text-foreground tabular-nums">{formatCurrency(account.balance)}</td></tr>)}</tbody></table></div>}</Panel>
    </PageContainer>
  );
}
