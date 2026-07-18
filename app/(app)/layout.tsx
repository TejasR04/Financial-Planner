import { AppShell } from "@/components/app-shell";
import { AuthGuard } from "@/components/auth-guard";
import { DataProvider } from "@/lib/data-provider";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <DataProvider>
        <AppShell>{children}</AppShell>
      </DataProvider>
    </AuthGuard>
  );
}
