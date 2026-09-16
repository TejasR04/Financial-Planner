"use client";

import { useEffect, useState } from "react";
import { FileUp, PencilLine, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DialogShell } from "@/components/ui/dialog-shell";
import {
  ApiError,
  api,
  type ApiCsvImportOverride,
  type ApiCsvImportPreview,
  type ApiCsvImportRow,
  type ApiTransaction,
} from "@/lib/api-client";
import type { Account } from "@/lib/data";
import { localDateKey } from "@/lib/local-date";

const inputClass = "mt-1 h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none focus:border-ring";
const MAX_FILE_BYTES = 5_000_000;

export function TransactionEntryDialog({ open, accounts, onClose, onSaved }: { open: boolean; accounts: Account[]; onClose: () => void; onSaved: (message: string) => void }) {
  const [mode, setMode] = useState<"manual" | "csv">("manual");
  const [accountId, setAccountId] = useState("");
  const [postedAt, setPostedAt] = useState(localDateKey);
  const [merchant, setMerchant] = useState("");
  const [category, setCategory] = useState("other");
  const [amount, setAmount] = useState("");
  const [type, setType] = useState<ApiTransaction["type"]>("expense");
  const [file, setFile] = useState<File | null>(null);
  const [csvText, setCsvText] = useState("");
  const [preview, setPreview] = useState<ApiCsvImportPreview | null>(null);
  const [previewRows, setPreviewRows] = useState<ApiCsvImportRow[]>([]);
  const [previewDirty, setPreviewDirty] = useState(false);
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
      setMerchant("");
      setAmount("");
      setCategory("other");
      onSaved("Transaction added.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't add that transaction.");
    } finally {
      setSaving(false);
    }
  };

  const overrides = (): ApiCsvImportOverride[] => previewRows.map((row) => ({
    row_number: row.row_number,
    include: !row.likely_duplicate,
    posted_at: row.posted_at,
    merchant: row.merchant,
    category: row.category,
    amount: row.amount,
    type: row.type,
  }));

  const loadPreview = async () => {
    if (!accountId || !file) throw new Error("Choose an account and a CSV file.");
    if (file.size > MAX_FILE_BYTES) throw new Error("That file is larger than 5 MB. Split it into smaller files.");
    const text = csvText || await file.text();
    const result = await api.transactions.previewCsv({
      account_id: accountId,
      csv_text: text,
      ...(preview ? { overrides: overrides() } : {}),
    });
    setCsvText(text);
    setPreview(result);
    setPreviewRows(result.rows);
    setPreviewDirty(false);
  };

  const submitCsv = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (!preview || previewDirty) {
        await loadPreview();
        return;
      }
      const result = await api.transactions.importCsv({
        account_id: accountId,
        csv_text: csvText,
        overrides: overrides(),
      });
      setFile(null);
      setCsvText("");
      setPreview(null);
      setPreviewRows([]);
      const skipped = result.skipped_duplicate_count
        ? ` ${result.skipped_duplicate_count} likely duplicate${result.skipped_duplicate_count === 1 ? " was" : "s were"} skipped.`
        : "";
      onSaved(`${result.imported_count} transaction${result.imported_count === 1 ? "" : "s"} imported.${skipped}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Couldn't import that CSV.");
    } finally {
      setSaving(false);
    }
  };

  const updatePreviewRow = (rowNumber: number, field: keyof ApiCsvImportRow, value: string) => {
    setPreviewRows((rows) => rows.map((row) => row.row_number === rowNumber ? { ...row, [field]: value } : row));
    setPreviewDirty(true);
  };

  const resetCsv = (nextFile: File | null) => {
    setFile(nextFile);
    setCsvText("");
    setPreview(null);
    setPreviewRows([]);
    setPreviewDirty(false);
    setError(null);
  };

  return <DialogShell onClose={onClose} closeDisabled={saving} ariaLabelledBy="transaction-entry-title" panelClassName="max-w-4xl">
    <div className="flex items-start justify-between border-b border-border px-4 py-3">
      <div><h2 id="transaction-entry-title" className="text-sm font-semibold text-foreground">Add transactions</h2><p className="mt-0.5 text-xs text-muted-foreground">Enter one transaction or review a bank CSV before importing it.</p></div>
      <Button type="button" variant="ghost" size="icon-sm" aria-label="Close" onClick={onClose} disabled={saving}><X /></Button>
    </div>
    <div className="flex gap-1 border-b border-border px-4 pt-3">
      <button type="button" onClick={() => setMode("manual")} className={mode === "manual" ? "border-b-2 border-primary px-2 pb-2 text-xs font-medium text-foreground" : "px-2 pb-2 text-xs text-muted-foreground"}><PencilLine className="mr-1 inline size-3.5" />Manual entry</button>
      <button type="button" onClick={() => setMode("csv")} className={mode === "csv" ? "border-b-2 border-primary px-2 pb-2 text-xs font-medium text-foreground" : "px-2 pb-2 text-xs text-muted-foreground"}><FileUp className="mr-1 inline size-3.5" />Import CSV</button>
    </div>
    {mode === "manual" ? <form onSubmit={submitManual} className="space-y-3 p-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3"><label className="text-xs font-medium text-muted-foreground">Account<select required value={accountId} onChange={(event) => setAccountId(event.target.value)} className={inputClass}><option value="" disabled>Choose account</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label><label className="text-xs font-medium text-muted-foreground">Date<input required type="date" value={postedAt} onChange={(event) => setPostedAt(event.target.value)} className={inputClass} /></label></div>
      <label className="block text-xs font-medium text-muted-foreground">Merchant or description<input required value={merchant} onChange={(event) => setMerchant(event.target.value)} className={inputClass} placeholder="e.g. Local grocery" /></label>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3"><label className="text-xs font-medium text-muted-foreground">Category<input required value={category} onChange={(event) => setCategory(event.target.value)} className={inputClass} placeholder="groceries" /></label><label className="text-xs font-medium text-muted-foreground">Type<select value={type} onChange={(event) => setType(event.target.value as ApiTransaction["type"])} className={inputClass}><option value="expense">Expense</option><option value="income">Income</option><option value="transfer">Transfer</option><option value="credit_card_payment">Credit card payment</option><option value="contribution">Contribution</option></select></label><label className="text-xs font-medium text-muted-foreground">Amount<input required type="number" step="0.01" min="0.01" inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} className={inputClass} placeholder="0.00" /></label></div>
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      <div className="flex justify-end gap-2"><Button type="button" variant="outline" size="sm" onClick={onClose} disabled={saving}>Cancel</Button><Button type="submit" size="sm" disabled={saving || !accounts.length}>{saving ? "Saving…" : "Add transaction"}</Button></div>
    </form> : <form onSubmit={submitCsv} className="space-y-3 p-4">
      <div className="grid gap-3 sm:grid-cols-2"><label className="block text-xs font-medium text-muted-foreground">Account<select required value={accountId} onChange={(event) => { setAccountId(event.target.value); setPreview(null); }} className={inputClass}><option value="" disabled>Choose account</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label><label className="block text-xs font-medium text-muted-foreground">CSV or TSV file<input required={!preview} type="file" accept=".csv,.tsv,text/csv,text/tab-separated-values" onChange={(event) => resetCsv(event.target.files?.[0] ?? null)} className="mt-1 block w-full text-xs text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-muted file:px-3 file:py-2 file:text-xs file:font-medium file:text-foreground" /></label></div>
      {!preview && <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground"><p className="font-medium text-foreground">Required columns</p><p className="mt-1 font-mono">date, merchant, category, amount</p><p className="mt-1">An optional <span className="font-mono">type</span> column can specify expense, income, transfer, credit_card_payment, or contribution. Files can contain up to 10,000 rows and 5 MB.</p><p className="mt-1">Duplicates use exact cents, similar merchant words, and posting dates within three days.</p></div>}
      {preview && <div className="space-y-2"><div className="flex items-center justify-between text-xs"><p><span className="font-medium text-foreground">{preview.importable_count}</span> ready to import · <span className="font-medium text-foreground">{preview.duplicate_count}</span> likely duplicates</p>{previewDirty && <p className="text-warning">Changes need to be rechecked.</p>}</div><div className="max-h-80 overflow-auto rounded-md border border-border"><table className="w-full min-w-[760px] text-xs"><thead className="sticky top-0 bg-muted"><tr><th className="px-2 py-2 text-left">Row</th><th className="px-2 py-2 text-left">Date</th><th className="px-2 py-2 text-left">Merchant</th><th className="px-2 py-2 text-left">Category</th><th className="px-2 py-2 text-left">Type</th><th className="px-2 py-2 text-right">Amount</th><th className="px-2 py-2 text-left">Status</th></tr></thead><tbody>{previewRows.map((row) => <tr key={row.row_number} className="border-t border-border align-top"><td className="px-2 py-2 font-mono">{row.row_number}</td><td className="px-2 py-1"><input type="date" value={row.posted_at} disabled={row.likely_duplicate} onChange={(event) => updatePreviewRow(row.row_number, "posted_at", event.target.value)} className="h-8 rounded border border-border bg-background px-1" /></td><td className="px-2 py-1"><input value={row.merchant} disabled={row.likely_duplicate} onChange={(event) => updatePreviewRow(row.row_number, "merchant", event.target.value)} className="h-8 w-44 rounded border border-border bg-background px-1" />{row.warnings.map((warning) => <p key={warning} className="mt-1 max-w-44 text-[10px] text-warning">{warning}</p>)}</td><td className="px-2 py-1"><input value={row.category} disabled={row.likely_duplicate} onChange={(event) => updatePreviewRow(row.row_number, "category", event.target.value)} className="h-8 w-32 rounded border border-border bg-background px-1" /></td><td className="px-2 py-1"><select value={row.type} disabled={row.likely_duplicate} onChange={(event) => updatePreviewRow(row.row_number, "type", event.target.value)} className="h-8 rounded border border-border bg-background px-1"><option value="expense">Expense</option><option value="income">Income</option><option value="transfer">Transfer</option><option value="credit_card_payment">Card payment</option><option value="contribution">Contribution</option></select></td><td className="px-2 py-1 text-right"><input type="number" step="0.01" value={row.amount} disabled={row.likely_duplicate} onChange={(event) => updatePreviewRow(row.row_number, "amount", event.target.value)} className="h-8 w-24 rounded border border-border bg-background px-1 text-right font-mono" /></td><td className="px-2 py-2">{row.likely_duplicate ? <span className="text-muted-foreground">Will skip</span> : <span className="text-positive">Ready</span>}</td></tr>)}</tbody></table></div></div>}
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      <div className="flex justify-end gap-2"><Button type="button" variant="outline" size="sm" onClick={onClose} disabled={saving}>Cancel</Button><Button type="submit" size="sm" disabled={saving || !accounts.length || (!!preview && !previewDirty && preview.importable_count === 0)}>{saving ? "Checking…" : !preview ? "Review import" : previewDirty ? "Recheck changes" : `Import ${preview.importable_count}`}</Button></div>
    </form>}
  </DialogShell>;
}
