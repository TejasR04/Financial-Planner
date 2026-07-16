"use client";

import { useState } from "react";
import { Check } from "lucide-react";
import { Panel, PanelHeader } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

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
  "h-8 w-full rounded-md border border-border bg-background px-2.5 text-[13px] text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-ring focus:ring-3 focus:ring-ring/20";

function Toggle({ defaultOn = false }: { defaultOn?: boolean }) {
  const [on, setOn] = useState(defaultOn);
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => setOn((v) => !v)}
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
                <input className={inputClass} defaultValue="Tejas Ravi" />
              </Field>
              <Field label="Email" hint="Used for alerts and reports">
                <input
                  className={inputClass}
                  type="email"
                  defaultValue="alex@meridian.finance"
                />
              </Field>
              <Field label="Base currency">
                <select className={inputClass} defaultValue="USD">
                  <option>USD — US Dollar</option>
                  <option>EUR — Euro</option>
                  <option>GBP — British Pound</option>
                </select>
              </Field>
              <Field label="Date of birth" hint="Drives retirement horizon">
                <input
                  className={inputClass}
                  type="text"
                  defaultValue="1993-04-18"
                />
              </Field>
            </div>
            <div className="flex justify-end gap-2 border-t border-border p-3">
              <Button variant="ghost" size="sm">
                Reset
              </Button>
              <Button size="sm">
                <Check />
                Save changes
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
                <input className={inputClass} type="number" defaultValue={62} />
              </Field>
              <Field
                label="Target equity allocation"
                hint="Used for drift alerts"
              >
                <input className={inputClass} type="number" defaultValue={42} />
              </Field>
              <Field label="Default withdrawal rate">
                <input
                  className={inputClass}
                  type="number"
                  step="0.1"
                  defaultValue={3.5}
                />
              </Field>
              <Field
                label="Include Social Security"
                hint="Add projected benefits to models"
              >
                <Toggle defaultOn />
              </Field>
            </div>
            <div className="flex justify-end gap-2 border-t border-border p-3">
              <Button size="sm">
                <Check />
                Save changes
              </Button>
            </div>
          </Panel>
        )}

        {tab === "institutions" && (
          <Panel>
            <PanelHeader
              title="Connected institutions"
              description="Data providers and sync cadence"
            />
            <ul className="divide-y divide-border">
              {[
                { name: "Fidelity", status: "Healthy", accounts: 1 },
                { name: "Vanguard", status: "Healthy", accounts: 1 },
                { name: "Charles Schwab", status: "Healthy", accounts: 1 },
                { name: "Chase", status: "Action required", accounts: 2 },
                { name: "Marcus", status: "Healthy", accounts: 1 },
              ].map((inst) => {
                const ok = inst.status === "Healthy";
                return (
                  <li
                    key={inst.name}
                    className="flex items-center justify-between gap-3 px-4 py-3"
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="flex size-7 items-center justify-center rounded-md border border-border bg-muted/50 font-mono text-[11px] font-semibold text-muted-foreground">
                        {inst.name.slice(0, 2).toUpperCase()}
                      </span>
                      <div>
                        <p className="text-[13px] font-medium text-foreground">
                          {inst.name}
                        </p>
                        <p className="text-[11px] text-muted-foreground">
                          {inst.accounts} account{inst.accounts > 1 ? "s" : ""}
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
                        {inst.status}
                      </span>
                      <Button variant="outline" size="xs">
                        Manage
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </Panel>
        )}

        {tab === "notifications" && (
          <Panel>
            <PanelHeader
              title="Notifications"
              description="Choose what Meridian alerts you about"
            />
            <div className="divide-y divide-border px-4">
              {[
                {
                  label: "Weekly portfolio digest",
                  hint: "Every Monday at 8:00 AM",
                  on: true,
                },
                {
                  label: "Allocation drift alerts",
                  hint: "When drift exceeds 5%",
                  on: true,
                },
                {
                  label: "Large transaction alerts",
                  hint: "Transactions over $2,500",
                  on: true,
                },
                {
                  label: "New AI recommendations",
                  hint: "When analysis surfaces opportunities",
                  on: false,
                },
                {
                  label: "Bill & contribution reminders",
                  hint: "Two days before due dates",
                  on: false,
                },
              ].map((n) => (
                <Field key={n.label} label={n.label} hint={n.hint}>
                  <div className="flex sm:justify-start">
                    <Toggle defaultOn={n.on} />
                  </div>
                </Field>
              ))}
            </div>
            <div className="flex justify-end gap-2 border-t border-border p-3">
              <Button size="sm">
                <Check />
                Save preferences
              </Button>
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}
