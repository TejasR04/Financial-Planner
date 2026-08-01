"use client";

import { usePathname } from "next/navigation";
import { Search, Sun, Moon, ChevronRight, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PlaidLinkButton } from "@/components/plaid-link-button";
import { KeyboardShortcut } from "@/components/keyboard-shortcut";
import { useTheme } from "@/components/theme-provider";
import { ApiError } from "@/lib/api-client";
import { useDataRefresh, useInstitutionsData } from "@/lib/data-provider";
import { requestPlaidRefresh } from "@/lib/plaid-sync";
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

export function Topbar({ onOpenCommand }: { onOpenCommand: () => void }) {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const institutions = useInstitutionsData();
  const refreshData = useDataRefresh();
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const title = titles[pathname] ?? "Overview";

  async function syncAll() {
    setSyncing(true);
    setSyncMessage(null);
    try {
      const result = await requestPlaidRefresh();
      const failures = result.data.filter((institution) => institution.error);
      refreshData();
      setSyncMessage(
        failures.length
          ? `${failures.length} need attention`
          : result.data.length
            ? `Synced ${result.data.length}`
            : "Nothing linked",
      );
    } catch (error) {
      setSyncMessage(error instanceof ApiError ? error.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur">
      <div className="flex items-center gap-1.5 text-[13px]">
        <span className="text-muted-foreground">Personal</span>
        <ChevronRight className="size-3.5 text-muted-foreground/50" />
        <span className="font-medium text-foreground">{title}</span>
      </div>

      <div className="flex flex-1 justify-center">
        <button
          type="button"
          onClick={onOpenCommand}
          className="group flex h-8 w-full max-w-[420px] items-center gap-2 rounded-md border border-border bg-muted/50 px-2.5 text-[13px] text-muted-foreground transition-colors hover:bg-muted"
        >
          <Search className="size-4 shrink-0" />
          <span className="flex-1 text-left">Search or run a command</span>
          <span className="rounded border border-border bg-background px-1.5 py-0.5"><KeyboardShortcut keyName="K" /></span>
        </button>
      </div>

      <div className="flex items-center gap-1">
        {syncMessage && (
          <span className="hidden max-w-40 truncate text-[11px] text-muted-foreground lg:inline" role="status">
            {syncMessage}
          </span>
        )}
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Sync all linked institutions"
          title={institutions.length ? "Sync all linked institutions" : "No linked institutions"}
          onClick={() => void syncAll()}
          disabled={syncing || institutions.length === 0}
        >
          <RefreshCw className={syncing ? "animate-spin" : undefined} />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Toggle theme"
          onClick={toggle}
        >
          {theme === "dark" ? <Sun /> : <Moon />}
        </Button>
        <PlaidLinkButton size="sm" className="ml-1" />
      </div>
    </header>
  );
}
