"use client";

import { useEffect, useState } from "react";
import { ThemeProvider } from "@/components/theme-provider";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";
import { CommandPalette } from "@/components/command-palette";
import { useDataError } from "@/lib/data-provider";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const dataError = useDataError();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <ThemeProvider>
      <div className="flex h-screen overflow-hidden bg-background text-foreground">
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar onOpenCommand={() => setCommandOpen(true)} />
          <main className="flex-1 overflow-y-auto">
            {dataError && (
              <div role="alert" className="border-b border-warning/30 bg-warning/10 px-5 py-2 text-xs text-foreground">
                {dataError}
              </div>
            )}
            {children}
          </main>
        </div>
      </div>
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
    </ThemeProvider>
  );
}
