"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DialogShell } from "@/components/ui/dialog-shell";
import { ApiError, api } from "@/lib/api-client";
import type { Account } from "@/lib/data";
import { useDataRefresh } from "@/lib/data-provider";

const typeOptions = [
  ["depository", "Cash / depository"],
  ["investment", "Investment"],
  ["retirement", "Retirement"],
  ["credit", "Credit card"],
  ["loan", "Loan"],
  ["property", "Property"],
] as const;

const apiTypeByDisplay: Record<Account["type"], (typeof typeOptions)[number][0]> = {
  Depository: "depository",
  Investment: "investment",
  Retirement: "retirement",
  Credit: "credit",
  Loan: "loan",
  Property: "property",
};

export function ManualAccountDialog({
  open,
  account,
  onClose,
}: {
  open: boolean;
  account: Account | null;
  onClose: () => void;
}) {
  const refresh = useDataRefresh();
  const [name, setName] = useState("");
  const [type, setType] = useState<(typeof typeOptions)[number][0]>("depository");
  const [balance, setBalance] = useState("");
  const [mask, setMask] = useState("");
  const [apy, setApy] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName(account?.name ?? "");
    setType(account ? apiTypeByDisplay[account.type] : "depository");
    setBalance(account ? String(account.balance) : "");
    setMask(account?.mask === "—" ? "" : account?.mask ?? "");
    setApy(account?.apy != null ? String(account.apy) : "");
    setError(null);
  }, [account, open]);

  if (!open) return null;
  const linked = Boolean(account?.institutionId);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (account) {
        await api.accounts.update(account.id, {
          name: name.trim(),
          ...(linked ? {} : { balance, mask: mask || undefined, apy: apy || undefined }),
        });
      } else {
        await api.accounts.create({
          name: name.trim(),
          type,
          balance,
          mask: mask || undefined,
          apy: apy || undefined,
        });
      }
      refresh();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save this account.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <DialogShell onClose={onClose} closeDisabled={saving} ariaLabelledBy="manual-account-title" panelClassName="max-w-md">
      <form onSubmit={submit}>
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h2 id="manual-account-title" className="text-sm font-semibold text-foreground">{account ? linked ? "Rename linked account" : "Edit manual account" : "Add manual account"}</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">{linked ? "Your name is kept locally; balances and account details continue to come from the institution." : "Amounts are recorded in USD."}</p>
          </div>
          <Button type="button" variant="ghost" size="icon-sm" aria-label="Close" onClick={onClose}><X /></Button>
        </div>
        <div className="space-y-3 p-4">
          <label className="block text-xs font-medium text-muted-foreground">Account name<input required value={name} onChange={(event) => setName(event.target.value)} className="mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none focus:border-ring" /></label>
          {!account && <label className="block text-xs font-medium text-muted-foreground">Account type<select value={type} onChange={(event) => setType(event.target.value as typeof type)} className="mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none focus:border-ring">{typeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
          {!linked && <><label className="block text-xs font-medium text-muted-foreground">Current balance<input required type="number" inputMode="decimal" step="0.01" value={balance} onChange={(event) => setBalance(event.target.value)} placeholder={type === "credit" || type === "loan" ? "Amount owed (for example, 2500)" : "0.00"} className="mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-ring" /></label>
          <div className="grid grid-cols-2 gap-3"><label className="block text-xs font-medium text-muted-foreground">Last four digits<span className="mt-1 block text-[11px] font-normal">Optional account identifier, not a PIN.</span><input inputMode="numeric" maxLength={4} value={mask} onChange={(event) => setMask(event.target.value.replace(/\D/g, "").slice(0, 4))} className="mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none focus:border-ring" /></label><label className="block text-xs font-medium text-muted-foreground">APY (optional)<div className="relative mt-1"><input type="number" inputMode="decimal" step="0.01" value={apy} onChange={(event) => setApy(event.target.value)} className="h-9 w-full rounded-md border border-border bg-background px-2 pr-7 text-sm text-foreground outline-none focus:border-ring" /><span className="pointer-events-none absolute right-2 top-2 text-sm text-muted-foreground">%</span></div></label></div></>}
          {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
        </div>
        <div className="flex justify-end gap-2 border-t border-border p-3"><Button type="button" variant="outline" size="sm" onClick={onClose} disabled={saving}>Cancel</Button><Button size="sm" type="submit" disabled={saving}>{saving ? "Saving…" : account ? "Save changes" : "Add account"}</Button></div>
      </form>
    </DialogShell>
  );
}
