import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { AuthGuard } from "@/components/auth-guard";
import { DataProvider } from "@/lib/data-provider";

export const metadata: Metadata = {
  title: "Overview — Meridian",
};

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <DataProvider>
        <AppShell>{children}</AppShell>
      </DataProvider>
    </AuthGuard>
  );
}
