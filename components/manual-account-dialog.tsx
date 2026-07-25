"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
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

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (account) {
        await api.accounts.update(account.id, {
          name: name.trim(),
          balance,
          mask: mask || undefined,
          apy: apy || undefined,
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/20 p-4 backdrop-blur-sm" onMouseDown={onClose}>
      <form className="w-full max-w-md rounded-xl border border-border bg-popover shadow-2xl" onSubmit={submit} onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">{account ? "Edit manual account" : "Add manual account"}</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">Amounts are recorded in USD.</p>
          </div>
          <Button type="button" variant="ghost" size="icon-sm" aria-label="Close" onClick={onClose}><X /></Button>
        </div>
        <div className="space-y-3 p-4">
          <label className="block text-xs font-medium text-muted-foreground">Account name<input required value={name} onChange={(event) => setName(event.target.value)} className="mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none focus:border-ring" /></label>
          {!account && <label className="block text-xs font-medium text-muted-foreground">Account type<select value={type} onChange={(event) => setType(event.target.value as typeof type)} className="mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none focus:border-ring">{typeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
          <label className="block text-xs font-medium text-muted-foreground">Current balance<input required inputMode="decimal" value={balance} onChange={(event) => setBalance(event.target.value)} placeholder={type === "credit" || type === "loan" ? "Amount owed (for example, 2500)" : "0.00"} className="mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-ring" /></label>
          <div className="grid grid-cols-2 gap-3"><label className="block text-xs font-medium text-muted-foreground">Last four digits<input maxLength={8} value={mask} onChange={(event) => setMask(event.target.value)} className="mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none focus:border-ring" /></label><label className="block text-xs font-medium text-muted-foreground">APY (optional)<input inputMode="decimal" value={apy} onChange={(event) => setApy(event.target.value)} className="mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none focus:border-ring" /></label></div>
          {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
        </div>
        <div className="flex justify-end gap-2 border-t border-border p-3"><Button type="button" variant="outline" size="sm" onClick={onClose} disabled={saving}>Cancel</Button><Button size="sm" type="submit" disabled={saving}>{saving ? "Saving…" : account ? "Save changes" : "Add account"}</Button></div>
      </form>
    </div>
  );
}
