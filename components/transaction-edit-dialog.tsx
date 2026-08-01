"use client";

import { useState } from "react";
import { api, ApiTransaction } from "@/lib/api-client";
import type { Account } from "@/lib/data";
import { Button } from "@/components/ui/button";
import { DialogShell } from "@/components/ui/dialog-shell";

const input = "h-8 w-full rounded-md border border-border bg-background px-2 text-xs";

export function TransactionEditDialog({ transaction, account, onClose, onSaved }: { transaction: ApiTransaction; account?: Account; onClose: () => void; onSaved: () => void }) {
  const linked = Boolean(account?.institutionId);
  const [values, setValues] = useState({ posted_at: transaction.posted_at, merchant: transaction.merchant, category: transaction.category, amount: transaction.amount, type: transaction.type });
  const [error, setError] = useState("");
  async function save() {
    try {
      await api.transactions.update(transaction.id, linked ? { category: values.category } : values);
      onSaved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update transaction.");
    }
  }
  const set = (key: keyof typeof values, value: string) => setValues({ ...values, [key]: value });
  return (
    <DialogShell onClose={onClose} ariaLabelledBy="transaction-edit-title" panelClassName="max-w-lg rounded-lg bg-card p-4">
      <h2 id="transaction-edit-title" className="text-sm font-semibold">Edit transaction</h2>
      <p className="mt-1 text-xs text-muted-foreground">{linked ? "Institution-owned details are read-only; your category remains editable." : "Manual and CSV transactions can be corrected."}</p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <input className={input} type="date" disabled={linked} value={values.posted_at} onChange={(event) => set("posted_at", event.target.value)} />
        <input className={input} disabled={linked} value={values.merchant} onChange={(event) => set("merchant", event.target.value)} />
        <input className={input} value={values.category} onChange={(event) => set("category", event.target.value)} />
        <input className={input} type="number" disabled={linked} value={values.amount} onChange={(event) => set("amount", event.target.value)} />
        <select className={input} disabled={linked} value={values.type} onChange={(event) => set("type", event.target.value)}>
          {["expense", "income", "transfer", "contribution"].map((type) => <option key={type}>{type}</option>)}
        </select>
      </div>
      {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
        <Button size="sm" onClick={() => void save()}>Save</Button>
      </div>
    </DialogShell>
  );
}
