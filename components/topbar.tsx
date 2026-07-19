"use client";

import { usePathname } from "next/navigation";
import { Search, Bell, Sun, Moon, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PlaidLinkButton } from "@/components/plaid-link-button";
import { useTheme } from "@/components/theme-provider";

const titles: Record<string, string> = {
  "/": "Overview",
  "/accounts": "Accounts",
  "/projections": "Projections",
  "/insights": "Insights",
  "/settings": "Settings",
};

export function Topbar({ onOpenCommand }: { onOpenCommand: () => void }) {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const title = titles[pathname] ?? "Overview";

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
          <kbd className="flex items-center gap-0.5 rounded border border-border bg-background px-1.5 py-0.5 font-mono text-[10px]">
            ⌘K
          </kbd>
        </button>
      </div>

      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Toggle theme"
          onClick={toggle}
        >
          {theme === "dark" ? <Sun /> : <Moon />}
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Notifications"
          className="relative"
        >
          <Bell />
          <span className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-primary" />
        </Button>
        <PlaidLinkButton size="sm" className="ml-1" />
      </div>
    </header>
  );
}
