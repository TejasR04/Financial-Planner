"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronsLeft, PiggyBank } from "lucide-react";
import { navGroups } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "flex shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200 ease-out",
        collapsed ? "w-[56px]" : "w-[236px]",
      )}
    >
      {/* Brand */}
      <div className="flex h-12 items-center gap-2 border-b border-sidebar-border px-3">
        <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <PiggyBank className="size-4" />
        </div>
        {!collapsed && (
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-[13px] font-semibold leading-tight text-sidebar-accent-foreground">
              Meridian
            </span>
            <span className="truncate text-[10px] leading-tight text-muted-foreground">
              Wealth Planning
            </span>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {navGroups.map((group) => (
          <div key={group.label} className="mb-4">
            {!collapsed && (
              <p className="px-2 pb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
                {group.label}
              </p>
            )}
            <ul className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const active = pathname === item.href;
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      title={collapsed ? item.label : undefined}
                      className={cn(
                        "group flex h-8 items-center gap-2.5 rounded-md px-2 text-[13px] font-medium transition-colors",
                        active
                          ? "bg-sidebar-accent text-sidebar-accent-foreground"
                          : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                        collapsed && "justify-center",
                      )}
                    >
                      <Icon
                        className={cn(
                          "size-4 shrink-0",
                          active
                            ? "text-primary"
                            : "text-muted-foreground group-hover:text-foreground",
                        )}
                      />
                      {!collapsed && (
                        <span className="flex-1 truncate">{item.label}</span>
                      )}
                      {!collapsed && item.shortcut && (
                        <span className="font-mono text-[10px] tracking-tight text-muted-foreground/60">
                          {item.shortcut}
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-sidebar-border p-2">
        {!collapsed && (
          <div className="mb-1.5 flex items-center gap-2.5 rounded-md px-2 py-1.5">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-chart-2/20 text-[11px] font-semibold text-chart-2">
              AV
            </div>
            <div className="flex min-w-0 flex-col">
              <span className="truncate text-xs font-medium text-sidebar-accent-foreground">
                Tejas Ravi
              </span>
              <span className="truncate text-[10px] text-muted-foreground">
                Analyst · Pro
              </span>
            </div>
          </div>
        )}
        <button
          type="button"
          onClick={onToggle}
          className={cn(
            "flex h-8 w-full items-center gap-2.5 rounded-md px-2 text-[13px] font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
            collapsed && "justify-center",
          )}
        >
          <ChevronsLeft
            className={cn(
              "size-4 shrink-0 transition-transform duration-200",
              collapsed && "rotate-180",
            )}
          />
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}
