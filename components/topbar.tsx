"use client";

import { useAuth } from "@/lib/auth-context";
import { usePathname } from "next/navigation";
import { Search, Sun, Moon, ChevronRight, RefreshCw, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PlaidLinkButton } from "@/components/plaid-link-button";
import { KeyboardShortcut } from "@/components/keyboard-shortcut";
import { useTheme } from "@/components/theme-provider";
import { ApiError } from "@/lib/api-client";
import { useDataRefresh } from "@/lib/data-provider";
import { requestDataRefresh } from "@/lib/plaid-sync";
import { useState } from "react";

const titles: Record<string, string> = {
  "/": "Overview",
  "/accounts": "Accounts",
  "/transactions": "Transactions",
  "/budget": "Budget",
  "/investments": "Investments",
  "/projections": "Projections",
  "/insights": "Insights",
  "/settings": "Settings",
};

export function Topbar({ onOpenCommand, onOpenNavigation }: { onOpenCommand: () => void; onOpenNavigation: () => void }) {
  const { isDemo, toggleDemo } = useAuth();
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const refreshData = useDataRefresh();
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<{ message: string; issues: string[] } | null>(null);
  const title = titles[pathname] ?? "Overview";

  async function syncAll() {
    setSyncing(true);
    setSyncStatus(null);
    try {
      const result = await requestDataRefresh();
      const issues = [
        ...result.institutions.flatMap((institution) => institution.error
          ? [`${institution.institution_name}: ${institution.error}`]
          : []),
        ...Object.entries(result.market.errors).map(([symbol, reason]) => `${symbol}: ${reason}`),
      ];
      refreshData();
      setSyncStatus({
        issues,
        message: issues.length
          ? `${issues.length} need attention`
          : result.institutions.length || result.market.holdings_updated || result.contributions_applied
            ? `Synced ${result.institutions.length} linked · ${result.market.holdings_updated} tickers · ${result.contributions_applied} contributions`
            : "Nothing to sync",
      });
    } catch (error) {
      setSyncStatus({ message: error instanceof ApiError ? error.message : "Sync failed", issues: [] });
    } finally {
      setSyncing(false);
    }
  }

  return (
    <header className="flex h-14 shrink-0 items-center gap-1 border-b border-border bg-background/80 px-2 backdrop-blur md:h-12 md:gap-3 md:px-4">
      <Button variant="ghost" size="icon" className="size-11 md:hidden" aria-label="Open navigation" aria-haspopup="dialog" onClick={onOpenNavigation}><Menu /></Button>
      <div className="flex min-w-0 flex-1 items-center gap-1.5 text-[13px] md:flex-none">
        <span className="hidden text-muted-foreground lg:inline">Personal</span>
        <ChevronRight className="hidden size-3.5 text-muted-foreground/50 lg:block" />
        <span className="truncate font-medium text-foreground">{title}</span>
      </div>

      <div className="flex shrink-0 justify-center md:flex-1">
        <button
          type="button"
          onClick={onOpenCommand}
          aria-label="Search or run a command"
          className="group flex size-11 items-center justify-center gap-2 rounded-md text-[13px] text-muted-foreground transition-colors hover:bg-muted md:h-8 md:w-full md:max-w-[420px] md:justify-start md:border md:border-border md:bg-muted/50 md:px-2.5"
        >
          <Search className="size-4 shrink-0" />
          <span className="hidden flex-1 text-left md:block">Search or run a command</span>
          <span className="hidden rounded border border-border bg-background px-1.5 py-0.5 lg:block"><KeyboardShortcut keyName="K" /></span>
        </button>
      </div>

      <div className="flex items-center gap-1">
        <Button variant="outline" size="sm" aria-pressed={isDemo} onClick={toggleDemo}>{isDemo ? "Exit demo" : "Demo mode"}</Button>
        {syncStatus && (syncStatus.issues.length > 0 ? (
          <details className="relative">
            <summary className="max-w-40 cursor-pointer list-none truncate rounded px-1.5 py-1 text-[11px] text-muted-foreground hover:bg-muted" aria-label={`${syncStatus.message}. Open sync issue details.`} title={syncStatus.message}>
              <span className="hidden lg:inline">{syncStatus.message}</span>
              <span className="lg:hidden">{syncStatus.issues.length} issue{syncStatus.issues.length === 1 ? "" : "s"}</span>
            </summary>
            <div className="absolute right-0 top-full z-50 mt-2 w-[min(20rem,calc(100vw-1rem))] rounded-md border border-border bg-popover p-3 text-xs text-popover-foreground shadow-lg">
              <p className="font-medium">Sync issues</p>
              <ul className="mt-2 space-y-1.5">
                {syncStatus.issues.map((issue, index) => <li key={`${index}-${issue}`} className="break-words">{issue}</li>)}
              </ul>
              <p className="mt-2 text-muted-foreground">Existing account and holding values were retained where updates failed.</p>
            </div>
          </details>
        ) : <span className="hidden max-w-40 truncate text-[11px] text-muted-foreground lg:inline" role="status">{syncStatus.message}</span>)}
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Sync all financial data"
          className="size-11 md:size-7"
          title="Sync linked institutions and automatic ticker prices"
          onClick={() => void syncAll()}
          disabled={isDemo || syncing}
        >
          <RefreshCw className={syncing ? "animate-spin" : undefined} />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Toggle theme"
          className="size-11 md:size-7"
          onClick={toggle}
        >
          {theme === "dark" ? <Sun /> : <Moon />}
        </Button>
        <PlaidLinkButton size="sm" className="size-11 px-0 md:ml-1 md:h-7 md:w-auto md:px-2.5" compactOnMobile />
      </div>
    </header>
  );
}
