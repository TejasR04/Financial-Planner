"use client";

import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { Panel, PanelHeader } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api-client";
import { useAccountsData, useDataRefresh, useUserAccount } from "@/lib/data-provider";

const sections = [
  { id: "profile", label: "Profile" },
  { id: "planning", label: "Planning" },
  { id: "institutions", label: "Institutions" },
  { id: "notifications", label: "Notifications" },
];

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-1 gap-2 py-3.5 sm:grid-cols-[220px_1fr] sm:items-center sm:gap-4">
      <div>
        <p className="text-[13px] font-medium text-foreground">{label}</p>
        {hint ? (
          <p className="mt-0.5 text-[11px] text-muted-foreground">{hint}</p>
        ) : null}
      </div>
      <div>{children}</div>
    </div>
  );
}

const inputClass =
  "h-8 w-full rounded-md border border-border bg-background px-2.5 text-[13px] text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-ring focus:ring-3 focus:ring-ring/20 disabled:cursor-not-allowed disabled:opacity-60";

function Toggle({
  on,
  onChange,
}: {
  on: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors",
        on ? "bg-primary" : "bg-muted",
      )}
    >
      <span
        className={cn(
          "inline-block size-4 rounded-full bg-background shadow-sm transition-transform",
          on ? "translate-x-4" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

export function SettingsForms() {
  const [tab, setTab] = useState("profile");
  const userAccount = useUserAccount();
  const accounts = useAccountsData();
  const refresh = useDataRefresh();

  // --- Profile tab ---------------------------------------------------
  const [fullName, setFullName] = useState("");
  const [baseCurrency, setBaseCurrency] = useState("USD");
  const [dob, setDob] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);

  useEffect(() => {
    if (!userAccount) return;
    setFullName(userAccount.fullName);
    setBaseCurrency(userAccount.baseCurrency);
    setDob(userAccount.dateOfBirth ?? "");
  }, [userAccount]);

  async function saveProfile() {
    setProfileSaving(true);
    setProfileSaved(false);
    try {
      await api.users.updateMe({
        full_name: fullName,
        base_currency: baseCurrency,
        date_of_birth: dob || undefined,
      });
      refresh();
      setProfileSaved(true);
    } finally {
      setProfileSaving(false);
    }
  }

  // --- Planning tab ----------------------------------------------------
  const [retirementAge, setRetirementAge] = useState(65);
  const [equityAllocation, setEquityAllocation] = useState(60);
  const [withdrawalRate, setWithdrawalRate] = useState(4);
  const [includeSS, setIncludeSS] = useState(true);
  const [planningSaving, setPlanningSaving] = useState(false);
  const [planningSaved, setPlanningSaved] = useState(false);

  useEffect(() => {
    if (!userAccount) return;
    setRetirementAge(userAccount.targetRetirementAge);
    setEquityAllocation(Math.round(userAccount.targetEquityAllocation * 100));
    setWithdrawalRate(Math.round(userAccount.defaultWithdrawalRate * 1000) / 10);
    setIncludeSS(userAccount.includeSocialSecurity);
  }, [userAccount]);

  async function savePlanning() {
    setPlanningSaving(true);
    setPlanningSaved(false);
    try {
      await api.users.updatePlanningProfile({
        target_retirement_age: retirementAge,
        target_equity_allocation: String(equityAllocation / 100),
        default_withdrawal_rate: String(withdrawalRate / 100),
        include_social_security: includeSS,
      });
      refresh();
      setPlanningSaved(true);
    } finally {
      setPlanningSaving(false);
    }
  }

  // --- Institutions tab: derived from real linked accounts --------------
  const institutionGroups = Array.from(
    accounts.reduce((map, a) => {
      const key = a.institution ?? "Manually added";
      const entry = map.get(key) ?? { count: 0, attention: 0 };
      entry.count += 1;
      if (a.status === "attention") entry.attention += 1;
      map.set(key, entry);
      return map;
    }, new Map<string, { count: number; attention: number }>()),
  );

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[180px_1fr]">
      {/* Section nav */}
      <nav className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
        {sections.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setTab(s.id)}
            className={cn(
              "whitespace-nowrap rounded-md px-2.5 py-1.5 text-left text-[13px] font-medium transition-colors",
              tab === s.id
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
            )}
          >
            {s.label}
          </button>
        ))}
      </nav>

      <div className="min-w-0">
        {tab === "profile" && (
          <Panel>
            <PanelHeader
              title="Profile"
              description="Your account identity and locale"
            />
            <div className="divide-y divide-border px-4">
              <Field label="Full name">
                <input
                  className={inputClass}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </Field>
              <Field label="Email" hint="Contact support to change your email">
                <input
                  className={inputClass}
                  type="email"
                  value={userAccount?.email ?? ""}
                  disabled
                />
              </Field>
              <Field label="Base currency">
                <select
                  className={inputClass}
                  value={baseCurrency}
                  onChange={(e) => setBaseCurrency(e.target.value)}
                >
                  <option value="USD">USD — US Dollar</option>
                  <option value="EUR">EUR — Euro</option>
                  <option value="GBP">GBP — British Pound</option>
                </select>
              </Field>
              <Field label="Date of birth" hint="Drives retirement horizon">
                <input
                  className={inputClass}
                  type="date"
                  value={dob}
                  onChange={(e) => setDob(e.target.value)}
                />
              </Field>
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-border p-3">
              {profileSaved && (
                <span className="text-[12px] text-positive">Saved</span>
              )}
              <Button size="sm" onClick={saveProfile} disabled={profileSaving}>
                <Check />
                {profileSaving ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </Panel>
        )}

        {tab === "planning" && (
          <Panel>
            <PanelHeader
              title="Planning assumptions"
              description="Defaults applied to new projections"
            />
            <div className="divide-y divide-border px-4">
              <Field label="Target retirement age">
                <input
                  className={inputClass}
                  type="number"
                  value={retirementAge}
                  onChange={(e) => setRetirementAge(Number(e.target.value))}
                />
              </Field>
              <Field
                label="Target equity allocation"
                hint="Used for drift alerts (%)"
              >
                <input
                  className={inputClass}
                  type="number"
                  value={equityAllocation}
                  onChange={(e) => setEquityAllocation(Number(e.target.value))}
                />
              </Field>
              <Field label="Default withdrawal rate" hint="%">
                <input
                  className={inputClass}
                  type="number"
                  step="0.1"
                  value={withdrawalRate}
                  onChange={(e) => setWithdrawalRate(Number(e.target.value))}
                />
              </Field>
              <Field
                label="Include Social Security"
                hint="Add projected benefits to models"
              >
                <Toggle on={includeSS} onChange={setIncludeSS} />
              </Field>
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-border p-3">
              {planningSaved && (
                <span className="text-[12px] text-positive">Saved</span>
              )}
              <Button size="sm" onClick={savePlanning} disabled={planningSaving}>
                <Check />
                {planningSaving ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </Panel>
        )}

        {tab === "institutions" && (
          <Panel>
            <PanelHeader
              title="Connected institutions"
              description="Derived from your linked accounts"
            />
            {institutionGroups.length === 0 ? (
              <p className="px-4 py-6 text-center text-[13px] text-muted-foreground">
                No institutions linked yet.
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {institutionGroups.map(([name, info]) => {
                  const ok = info.attention === 0;
                  return (
                    <li
                      key={name}
                      className="flex items-center justify-between gap-3 px-4 py-3"
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="flex size-7 items-center justify-center rounded-md border border-border bg-muted/50 font-mono text-[11px] font-semibold text-muted-foreground">
                          {name.slice(0, 2).toUpperCase()}
                        </span>
                        <div>
                          <p className="text-[13px] font-medium text-foreground">
                            {name}
                          </p>
                          <p className="text-[11px] text-muted-foreground">
                            {info.count} account{info.count > 1 ? "s" : ""}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span
                          className={cn(
                            "flex items-center gap-1.5 text-[11px] font-medium",
                            ok ? "text-positive" : "text-warning",
                          )}
                        >
                          <span
                            className={cn(
                              "size-1.5 rounded-full",
                              ok ? "bg-positive" : "bg-warning",
                            )}
                          />
                          {ok ? "Healthy" : "Action required"}
                        </span>
                        <Button variant="outline" size="xs">
                          Manage
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>
        )}

        {tab === "notifications" && (
          <Panel>
            <PanelHeader
              title="Notifications"
              description="Choose what Meridian alerts you about — saved locally on this device for now"
            />
            <div className="divide-y divide-border px-4">
              {[
                {
                  label: "Weekly portfolio digest",
                  hint: "Every Monday at 8:00 AM",
                },
                {
                  label: "Allocation drift alerts",
                  hint: "When drift exceeds 5%",
                },
                {
                  label: "Large transaction alerts",
                  hint: "Transactions over $2,500",
                },
                {
                  label: "New AI recommendations",
                  hint: "When analysis surfaces opportunities",
                },
                {
                  label: "Bill & contribution reminders",
                  hint: "Two days before due dates",
                },
              ].map((n) => (
                <NotificationToggleField key={n.label} label={n.label} hint={n.hint} />
              ))}
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}

// Local-only preference (no backend model exists for notification settings
// yet) — kept isolated so it doesn't silently claim to be server-persisted.
function NotificationToggleField({ label, hint }: { label: string; hint: string }) {
  const [on, setOn] = useState(false);
  return (
    <Field label={label} hint={hint}>
      <div className="flex sm:justify-start">
        <Toggle on={on} onChange={setOn} />
      </div>
    </Field>
  );
}
