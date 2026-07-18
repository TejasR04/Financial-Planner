"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api-client";
import { Button } from "@/components/ui/button";

const inputClass =
  "h-9 w-full rounded-md border border-border bg-background px-3 text-[13px] text-foreground outline-none transition-colors focus:border-ring focus:ring-3 focus:ring-ring/20";

export default function OnboardingPage() {
  const { status } = useAuth();
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [baseCurrency, setBaseCurrency] = useState("USD");
  const [dob, setDob] = useState("");
  const [retirementAge, setRetirementAge] = useState(65);
  const [equityAllocation, setEquityAllocation] = useState(60);
  const [withdrawalRate, setWithdrawalRate] = useState(4);
  const [includeSS, setIncludeSS] = useState(true);

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
      return;
    }
    if (status !== "authenticated") return;

    let cancelled = false;
    (async () => {
      try {
        const [user, profile] = await Promise.all([
          api.users.me(),
          api.users.planningProfile(),
        ]);
        if (cancelled) return;
        setFullName(user.full_name);
        setBaseCurrency(user.base_currency);
        setDob(user.date_of_birth ?? "");
        setRetirementAge(profile.target_retirement_age);
        setEquityAllocation(Math.round(parseFloat(profile.target_equity_allocation) * 100));
        setWithdrawalRate(Math.round(parseFloat(profile.default_withdrawal_rate) * 1000) / 10);
        setIncludeSS(profile.include_social_security);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [status, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await Promise.all([
        api.users.updateMe({
          full_name: fullName,
          base_currency: baseCurrency,
          date_of_birth: dob || undefined,
        }),
        api.users.updatePlanningProfile({
          target_retirement_age: retirementAge,
          target_equity_allocation: String(equityAllocation / 100),
          default_withdrawal_rate: String(withdrawalRate / 100),
          include_social_security: includeSS,
        }),
      ]);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save your details.");
      setSaving(false);
    }
  }

  if (status !== "authenticated" || loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <p className="text-[13px] text-muted-foreground">Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-lg">
        <div className="mb-6">
          <p className="text-lg font-semibold tracking-tight text-foreground">
            Let&apos;s set up your plan
          </p>
          <p className="mt-1 text-[13px] text-muted-foreground">
            A few real details make every projection accurate from day one.
            You can change these anytime in Settings.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-5 rounded-lg border border-border bg-card p-5"
        >
          <div>
            <p className="mb-3 text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
              About you
            </p>
            <div className="flex flex-col gap-3">
              <div>
                <label className="text-[13px] text-foreground">Full name</label>
                <input
                  className={`${inputClass} mt-1.5`}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[13px] text-foreground">Date of birth</label>
                  <input
                    className={`${inputClass} mt-1.5`}
                    type="date"
                    value={dob}
                    onChange={(e) => setDob(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="text-[13px] text-foreground">Base currency</label>
                  <select
                    className={`${inputClass} mt-1.5`}
                    value={baseCurrency}
                    onChange={(e) => setBaseCurrency(e.target.value)}
                  >
                    <option value="USD">USD — US Dollar</option>
                    <option value="EUR">EUR — Euro</option>
                    <option value="GBP">GBP — British Pound</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          <div>
            <p className="mb-3 text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
              Retirement plan
            </p>
            <div className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[13px] text-foreground">Target retirement age</label>
                  <input
                    className={`${inputClass} mt-1.5`}
                    type="number"
                    value={retirementAge}
                    onChange={(e) => setRetirementAge(Number(e.target.value))}
                    min={30}
                    max={90}
                  />
                </div>
                <div>
                  <label className="text-[13px] text-foreground">Target equity %</label>
                  <input
                    className={`${inputClass} mt-1.5`}
                    type="number"
                    value={equityAllocation}
                    onChange={(e) => setEquityAllocation(Number(e.target.value))}
                    min={0}
                    max={100}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 items-end gap-3">
                <div>
                  <label className="text-[13px] text-foreground">Withdrawal rate %</label>
                  <input
                    className={`${inputClass} mt-1.5`}
                    type="number"
                    step="0.1"
                    value={withdrawalRate}
                    onChange={(e) => setWithdrawalRate(Number(e.target.value))}
                  />
                </div>
                <label className="flex h-9 items-center gap-2 text-[13px] text-foreground">
                  <input
                    type="checkbox"
                    checked={includeSS}
                    onChange={(e) => setIncludeSS(e.target.checked)}
                    className="size-4 rounded border-border"
                  />
                  Include Social Security
                </label>
              </div>
            </div>
          </div>

          {error && (
            <p className="text-[12px] text-destructive" role="alert">
              {error}
            </p>
          )}

          <div className="flex items-center justify-between gap-2 border-t border-border pt-4">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => router.push("/")}
              disabled={saving}
            >
              Skip for now
            </Button>
            <Button type="submit" size="sm" disabled={saving}>
              {saving ? "Saving…" : "Save and continue"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
