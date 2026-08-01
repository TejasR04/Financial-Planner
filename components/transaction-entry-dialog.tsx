"use client";

import { useEffect, useState } from "react";
import { FileUp, PencilLine, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DialogShell } from "@/components/ui/dialog-shell";
import { ApiError, api, type ApiTransaction } from "@/lib/api-client";
import type { Account } from "@/lib/data";
import { localDateKey } from "@/lib/local-date";

const inputClass = "mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none focus:border-ring";
export function TransactionEntryDialog({ open, accounts, onClose, onSaved }: { open: boolean; accounts: Account[]; onClose: () => void; onSaved: (message: string) => void }) {
  const [mode, setMode] = useState<"manual" | "csv">("manual");
  const [accountId, setAccountId] = useState("");
  const [postedAt, setPostedAt] = useState(localDateKey);
  const [merchant, setMerchant] = useState("");
  const [category, setCategory] = useState("other");
  const [amount, setAmount] = useState("");
  const [type, setType] = useState<ApiTransaction["type"]>("expense");
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setAccountId((current) => current || accounts[0]?.id || "");
    setError(null);
  }, [accounts, open]);

  if (!open) return null;

  const submitManual = async (event: React.FormEvent) => {
    event.preventDefault();
    const parsedAmount = Number(amount);
    if (!accountId || !Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      setError("Choose an account and enter an amount greater than zero.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.transactions.create({
        account_id: accountId,
        posted_at: postedAt,
        merchant: merchant.trim(),
        category: category.trim() || "other",
        amount: String(type === "expense" ? -Math.abs(parsedAmount) : Math.abs(parsedAmount)),
        type,
        status: "cleared",
      });
      setMerchant(""); setAmount(""); setCategory("other");
      onSaved("Transaction added.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't add that transaction.");
    } finally { setSaving(false); }
  };

  const submitCsv = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!accountId || !file) { setError("Choose an account and a CSV file."); return; }
    setSaving(true);
    setError(null);
    try {
      const csvText = await file.text();
      const result = await api.transactions.importCsv({ account_id: accountId, csv_text: csvText });
      setFile(null);
      onSaved(`${result.imported_count} transaction${result.imported_count === 1 ? "" : "s"} imported.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't import that CSV.");
    } finally { setSaving(false); }
  };

  return <DialogShell onClose={onClose} closeDisabled={saving} ariaLabelledBy="transaction-entry-title" panelClassName="max-w-lg">
      <div className="flex items-start justify-between border-b border-border px-4 py-3"><div><h2 id="transaction-entry-title" className="text-sm font-semibold text-foreground">Add transactions</h2><p className="mt-0.5 text-xs text-muted-foreground">Enter one transaction or import a bank CSV into an existing account.</p></div><Button type="button" variant="ghost" size="icon-sm" aria-label="Close" onClick={onClose} disabled={saving}><X /></Button></div>
      <div className="flex gap-1 border-b border-border px-4 pt-3"><button type="button" onClick={() => setMode("manual")} className={mode === "manual" ? "border-b-2 border-primary px-2 pb-2 text-xs font-medium text-foreground" : "px-2 pb-2 text-xs text-muted-foreground"}><PencilLine className="mr-1 inline size-3.5" />Manual entry</button><button type="button" onClick={() => setMode("csv")} className={mode === "csv" ? "border-b-2 border-primary px-2 pb-2 text-xs font-medium text-foreground" : "px-2 pb-2 text-xs text-muted-foreground"}><FileUp className="mr-1 inline size-3.5" />Import CSV</button></div>
      {mode === "manual" ? <form onSubmit={submitManual} className="space-y-3 p-4"><div className="grid grid-cols-2 gap-3"><label className="text-xs font-medium text-muted-foreground">Account<select required value={accountId} onChange={(event) => setAccountId(event.target.value)} className={inputClass}><option value="" disabled>Choose account</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label><label className="text-xs font-medium text-muted-foreground">Date<input required type="date" value={postedAt} onChange={(event) => setPostedAt(event.target.value)} className={inputClass} /></label></div><label className="block text-xs font-medium text-muted-foreground">Merchant or description<input required value={merchant} onChange={(event) => setMerchant(event.target.value)} className={inputClass} placeholder="e.g. Local grocery" /></label><div className="grid grid-cols-3 gap-3"><label className="text-xs font-medium text-muted-foreground">Category<input required value={category} onChange={(event) => setCategory(event.target.value)} className={inputClass} placeholder="groceries" /></label><label className="text-xs font-medium text-muted-foreground">Type<select value={type} onChange={(event) => setType(event.target.value as ApiTransaction["type"])} className={inputClass}><option value="expense">Expense</option><option value="income">Income</option><option value="transfer">Transfer</option><option value="contribution">Contribution</option></select></label><label className="text-xs font-medium text-muted-foreground">Amount<input required inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} className={inputClass} placeholder="0.00" /></label></div>{error && <p role="alert" className="text-xs text-destructive">{error}</p>}<div className="flex justify-end gap-2"><Button type="button" variant="outline" size="sm" onClick={onClose} disabled={saving}>Cancel</Button><Button type="submit" size="sm" disabled={saving || !accounts.length}>{saving ? "Saving…" : "Add transaction"}</Button></div></form> : <form onSubmit={submitCsv} className="space-y-3 p-4"><label className="block text-xs font-medium text-muted-foreground">Account<select required value={accountId} onChange={(event) => setAccountId(event.target.value)} className={inputClass}><option value="" disabled>Choose account</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label><label className="block text-xs font-medium text-muted-foreground">CSV file<input required type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="mt-1 block w-full text-xs text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-muted file:px-3 file:py-2 file:text-xs file:font-medium file:text-foreground" /></label><div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground"><p className="font-medium text-foreground">Required columns</p><p className="mt-1 font-mono">date, merchant, category, amount</p><p className="mt-1">Use YYYY-MM-DD or MM/DD/YYYY. Expenses should be negative and income positive.</p></div>{error && <p role="alert" className="text-xs text-destructive">{error}</p>}<div className="flex justify-end gap-2"><Button type="button" variant="outline" size="sm" onClick={onClose} disabled={saving}>Cancel</Button><Button type="submit" size="sm" disabled={saving || !accounts.length}>{saving ? "Importing…" : "Import transactions"}</Button></div></form>}
  </DialogShell>;
}
