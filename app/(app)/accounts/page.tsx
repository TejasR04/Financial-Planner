"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { PageContainer, PageHeader } from "@/components/page-container";
import { Panel, PanelHeader } from "@/components/panel";
import { AccountCard } from "@/components/account-card";
import { Button } from "@/components/ui/button";
import { PlaidLinkButton } from "@/components/plaid-link-button";
import { formatCurrency } from "@/lib/data";
import { ApiError, api } from "@/lib/api-client";
import { useAccountsData, useDataRefresh } from "@/lib/data-provider";

type SyncFeedback =
  | {
      tone: "success" | "error";
      message: string;
      reconnectInstitution?: { id: string; name: string };
    }
  | null;

// Development Strict Mode and a quick click can overlap page effects. Keep
// one browser-wide Plaid refresh in flight so both triggers await the same
// response instead of racing the cursor-based backend sync.
let activePlaidRefresh: ReturnType<typeof api.plaid.refresh> | null = null;

function requestPlaidRefresh() {
  if (activePlaidRefresh === null) {
    activePlaidRefresh = api.plaid.refresh().finally(() => {
      activePlaidRefresh = null;
    });
  }
  return activePlaidRefresh;
}

export default function AccountsPage() {
  const accounts = useAccountsData();
  const refreshData = useDataRefresh();
  const [syncing, setSyncing] = useState(false);
  const [syncFeedback, setSyncFeedback] = useState<SyncFeedback>(null);
  const hasAutoSynced = useRef(false);

  const syncAll = useCallback(async () => {
    setSyncing(true);
    setSyncFeedback(null);
    try {
      const result = await requestPlaidRefresh();
      refreshData();

      const failures = result.data.filter((institution) => institution.error);
      const syncedAccounts = result.data.reduce(
        (total, institution) => total + institution.accounts_synced,
        0,
      );
      if (failures.length > 0) {
        setSyncFeedback({
          tone: "error",
          message: `${failures.length} institution${failures.length === 1 ? "" : "s"} needs attention. ${failures[0].institution_name}: ${failures[0].error}`,
          reconnectInstitution: {
            id: failures[0].institution_id,
            name: failures[0].institution_name,
          },
        });
      } else if (result.data.length === 0) {
        setSyncFeedback({
          tone: "success",
          message: "No linked institutions to sync.",
        });
      } else {
        setSyncFeedback({
          tone: "success",
          message: `Synced ${syncedAccounts} account${syncedAccounts === 1 ? "" : "s"} across ${result.data.length} institution${result.data.length === 1 ? "" : "s"}.`,
        });
      }
    } catch (error) {
      setSyncFeedback({
        tone: "error",
        message:
          error instanceof ApiError
            ? error.message
            : "Couldn't sync your linked institutions. Try again.",
      });
    } finally {
      setSyncing(false);
    }
  }, [refreshData]);

  useEffect(() => {
    if (hasAutoSynced.current) return;
    hasAutoSynced.current = true;
    void syncAll();
  }, [syncAll]);

  const assets = accounts
    .filter((a) => a.balance >= 0)
    .reduce((s, a) => s + a.balance, 0);
  const liabilities = accounts
    .filter((a) => a.balance < 0)
    .reduce((s, a) => s + a.balance, 0);
  const net = assets + liabilities;

  const summary = [
    {
      label: "Total assets",
      value: formatCurrency(assets),
      tint: "text-foreground",
    },
    {
      label: "Total liabilities",
      value: formatCurrency(liabilities),
      tint: "text-destructive",
    },
    { label: "Net worth", value: formatCurrency(net), tint: "text-primary" },
  ];

  const assetAccounts = accounts.filter((a) => a.balance >= 0);
  const liabilityAccounts = accounts.filter((a) => a.balance < 0);
  const institutionCount = new Set(
    accounts.map((a) => a.institution).filter(Boolean),
  ).size;

  return (
    <PageContainer>
      <PageHeader
        title="Accounts"
        description={`${accounts.length} linked account${accounts.length === 1 ? "" : "s"}${
          institutionCount ? ` across ${institutionCount} institution${institutionCount === 1 ? "" : "s"}` : ""
        }`}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void syncAll()} disabled={syncing}>
              <RefreshCw className={syncing ? "animate-spin" : undefined} />
              {syncing ? "Syncing..." : "Sync all"}
            </Button>
            <PlaidLinkButton size="sm" />
          </>
        }
      />

      {syncFeedback && (
        <div
          role="status"
          className={`mt-3 flex flex-wrap items-center gap-2 text-xs ${syncFeedback.tone === "error" ? "text-destructive" : "text-positive"}`}
        >
          <span>{syncFeedback.message}</span>
          {syncFeedback.reconnectInstitution && (
            <PlaidLinkButton
              label={`Reconnect ${syncFeedback.reconnectInstitution.name}`}
              institutionId={syncFeedback.reconnectInstitution.id}
              onLinked={() =>
                setSyncFeedback({
                  tone: "success",
                  message: `${syncFeedback.reconnectInstitution?.name} is reconnected and synced.`,
                })
              }
              size="xs"
              variant="outline"
            />
          )}
        </div>
      )}

      {/* Summary strip */}
      <div className="grid grid-cols-1 divide-y divide-border overflow-hidden rounded-lg border border-border bg-card sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        {summary.map((s) => (
          <div key={s.label} className="px-5 py-4">
            <p className="text-xs font-medium text-muted-foreground">
              {s.label}
            </p>
            <p
              className={`mt-1.5 font-mono text-2xl font-semibold tracking-tight tabular-nums ${s.tint}`}
            >
              {s.value}
            </p>
          </div>
        ))}
      </div>

      {/* Assets */}
      <div className="mt-6 flex items-center justify-between">
        <h2 className="text-[13px] font-semibold tracking-tight text-foreground">
          Assets
        </h2>
        <span className="font-mono text-xs text-muted-foreground tabular-nums">
          {assetAccounts.length} accounts ·{" "}
          {formatCurrency(assets, { compact: true })}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {assetAccounts.map((a) => (
          <AccountCard key={a.id} account={a} />
        ))}
      </div>

      {/* Liabilities */}
      <div className="mt-6 flex items-center justify-between">
        <h2 className="text-[13px] font-semibold tracking-tight text-foreground">
          Liabilities
        </h2>
        <span className="font-mono text-xs text-muted-foreground tabular-nums">
          {liabilityAccounts.length} accounts ·{" "}
          {formatCurrency(liabilities, { compact: true })}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {liabilityAccounts.map((a) => (
          <AccountCard key={a.id} account={a} />
        ))}
      </div>

      {/* Full ledger */}
      <Panel className="mt-6">
        <PanelHeader
          title="All positions"
          description="Complete account ledger with sync status"
        />
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-border text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-2 font-medium">Account</th>
                <th className="px-4 py-2 font-medium">Type</th>
                <th className="hidden px-4 py-2 font-medium md:table-cell">
                  Institution
                </th>
                <th className="hidden px-4 py-2 font-medium lg:table-cell">
                  Updated
                </th>
                <th className="px-4 py-2 text-right font-medium">Balance</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr
                  key={a.id}
                  className="border-b border-border/60 transition-colors last:border-0 hover:bg-muted/40"
                >
                  <td className="px-4 py-2.5">
                    <span className="font-medium text-foreground">
                      {a.name}
                    </span>
                    <span className="ml-1.5 font-mono text-[11px] text-muted-foreground">
                      ••{a.mask}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">
                    {a.type}
                  </td>
                  <td className="hidden px-4 py-2.5 text-muted-foreground md:table-cell">
                    {a.institution ?? "—"}
                  </td>
                  <td className="hidden px-4 py-2.5 font-mono text-xs text-muted-foreground tabular-nums lg:table-cell">
                    {a.updated}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-right font-mono font-medium text-foreground tabular-nums">
                    {formatCurrency(a.balance)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </PageContainer>
  );
}
