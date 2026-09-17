"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { status, isDemo } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated" && !isDemo) {
      router.replace("/login");
    }
  }, [status, router, isDemo]);

  if (status !== "authenticated" && !isDemo) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <p className="text-[13px] text-muted-foreground">Loading…</p>
      </div>
    );
  }

  return <div key={isDemo ? "demo" : "personal"} className="contents">{children}</div>;
}
