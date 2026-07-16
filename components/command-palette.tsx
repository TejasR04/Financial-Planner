"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  CornerDownLeft,
  LayoutDashboard,
  Wallet,
  TrendingUp,
  Sparkles,
  Settings,
  Plus,
  Download,
  Sun,
  Moon,
  type LucideIcon,
} from "lucide-react";
import { useTheme } from "@/components/theme-provider";
import { cn } from "@/lib/utils";

type Command = {
  id: string;
  label: string;
  group: string;
  icon: LucideIcon;
  keywords?: string;
  run: () => void;
};

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const { theme, toggle } = useTheme();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands = useMemo<Command[]>(() => {
    const go = (href: string) => () => {
      router.push(href);
      onOpenChange(false);
    };
    return [
      {
        id: "nav-overview",
        label: "Go to Overview",
        group: "Navigation",
        icon: LayoutDashboard,
        run: go("/"),
      },
      {
        id: "nav-accounts",
        label: "Go to Accounts",
        group: "Navigation",
        icon: Wallet,
        run: go("/accounts"),
      },
      {
        id: "nav-projections",
        label: "Go to Projections",
        group: "Navigation",
        icon: TrendingUp,
        run: go("/projections"),
      },
      {
        id: "nav-insights",
        label: "Go to Insights",
        group: "Navigation",
        icon: Sparkles,
        run: go("/insights"),
      },
      {
        id: "nav-settings",
        label: "Go to Settings",
        group: "Navigation",
        icon: Settings,
        run: go("/settings"),
      },
      {
        id: "act-link",
        label: "Link a new account",
        group: "Actions",
        icon: Plus,
        run: () => onOpenChange(false),
      },
      {
        id: "act-export",
        label: "Export financial report",
        group: "Actions",
        icon: Download,
        run: () => onOpenChange(false),
      },
      {
        id: "act-theme",
        label:
          theme === "dark" ? "Switch to light theme" : "Switch to dark theme",
        group: "Actions",
        icon: theme === "dark" ? Sun : Moon,
        keywords: "dark light appearance",
        run: () => {
          toggle();
          onOpenChange(false);
        },
      },
    ];
  }, [router, onOpenChange, theme, toggle]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) =>
      `${c.label} ${c.group} ${c.keywords ?? ""}`.toLowerCase().includes(q),
    );
  }, [commands, query]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  if (!open) return null;

  const groups = filtered.reduce<Record<string, Command[]>>((acc, c) => {
    (acc[c.group] ??= []).push(c);
    return acc;
  }, {});

  let runningIndex = -1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-foreground/20 pt-[12vh] backdrop-blur-[2px]"
      onMouseDown={() => onOpenChange(false)}
    >
      <div
        className="w-full max-w-[560px] overflow-hidden rounded-xl border border-border bg-popover shadow-2xl shadow-foreground/10"
        onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => Math.min(a + 1, filtered.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
          } else if (e.key === "Enter") {
            e.preventDefault();
            filtered[active]?.run();
          } else if (e.key === "Escape") {
            onOpenChange(false);
          }
        }}
      >
        <div className="flex items-center gap-2.5 border-b border-border px-3.5">
          <Search className="size-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search commands, accounts, actions…"
            className="h-11 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
          <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            ESC
          </kbd>
        </div>

        <div className="max-h-[340px] overflow-y-auto p-1.5">
          {filtered.length === 0 ? (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">
              No results for &ldquo;{query}&rdquo;
            </p>
          ) : (
            Object.entries(groups).map(([group, items]) => (
              <div key={group} className="mb-1">
                <p className="px-2.5 py-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
                  {group}
                </p>
                {items.map((c) => {
                  runningIndex += 1;
                  const idx = runningIndex;
                  const Icon = c.icon;
                  const isActive = idx === active;
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onMouseEnter={() => setActive(idx)}
                      onClick={() => c.run()}
                      className={cn(
                        "flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-[13px] transition-colors",
                        isActive
                          ? "bg-accent text-accent-foreground"
                          : "text-foreground",
                      )}
                    >
                      <Icon
                        className={cn(
                          "size-4 shrink-0",
                          isActive ? "text-primary" : "text-muted-foreground",
                        )}
                      />
                      <span className="flex-1">{c.label}</span>
                      {isActive && (
                        <CornerDownLeft className="size-3.5 text-muted-foreground" />
                      )}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
