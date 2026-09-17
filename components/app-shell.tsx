"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useState } from "react";
import { ThemeProvider } from "@/components/theme-provider";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";
import { CommandPalette } from "@/components/command-palette";
import { useDataError } from "@/lib/data-provider";
import { DialogShell } from "@/components/ui/dialog-shell";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isDemo } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const dataError = useDataError();

  useEffect(() => {
    const media = window.matchMedia("(min-width: 768px)");
    const closeOnDesktop = () => { if (media.matches) setMobileOpen(false); };
    media.addEventListener("change", closeOnDesktop);
    return () => media.removeEventListener("change", closeOnDesktop);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mac = /Mac|iPhone|iPad|iPod/i.test(navigator.userAgent);
      const modifier = mac ? e.metaKey : e.ctrlKey;
      if (modifier && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setMobileOpen(false);
        setCommandOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <ThemeProvider>
      <div className="flex h-dvh overflow-hidden bg-background text-foreground" inert={mobileOpen}>
        <div className="hidden md:flex">
          <Sidebar
            collapsed={collapsed}
            onToggle={() => setCollapsed((c) => !c)}
          />
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar onOpenCommand={() => setCommandOpen(true)} onOpenNavigation={() => setMobileOpen(true)} />
          <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">
            {isDemo && <div role="status" className="border-b border-primary/20 bg-primary/10 px-5 py-2 text-xs">Demo mode: sample data only. Edits reset on exit or reload. Projections are illustrative. Gemini and bank connections are disabled.</div>}
            {dataError && (
              <div role="alert" className="border-b border-warning/30 bg-warning/10 px-5 py-2 text-xs text-foreground">
                {dataError}
              </div>
            )}
            {children}
          </main>
        </div>
      </div>
      {mobileOpen && (
        <DialogShell ariaLabel="Navigation" onClose={() => setMobileOpen(false)}
          overlayClassName="justify-start p-0"
          panelClassName="h-dvh max-h-dvh w-[min(280px,85vw)] rounded-none border-0">
          <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} mobile onNavigate={() => setMobileOpen(false)} />
        </DialogShell>
      )}
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
    </ThemeProvider>
  );
}
