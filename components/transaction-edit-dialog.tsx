"use client";

import { useEffect, useState } from "react";
import { api, ApiBudgetCategory, ApiTransaction } from "@/lib/api-client";
import type { Account } from "@/lib/data";
import { Button } from "@/components/ui/button";
import { DialogShell } from "@/components/ui/dialog-shell";

const input = "h-8 w-full rounded-md border border-border bg-background px-2 text-xs";

export function TransactionEditDialog({ transaction, account, onClose, onSaved }: { transaction: ApiTransaction; account?: Account; onClose: () => void; onSaved: () => void }) {
  const [values, setValues] = useState({ posted_at: transaction.posted_at, merchant: transaction.merchant, category: transaction.category, amount: transaction.amount, type: transaction.type });
  const [categories, setCategories] = useState<ApiBudgetCategory[]>([]);
  const [budgetCategoryId, setBudgetCategoryId] = useState(transaction.budget_category_id ?? "");
  const [error, setError] = useState("");
  useEffect(() => { void api.budgets.categories().then(setCategories).catch(() => setCategories([])); }, []);
  async function save() {
    try {
      const linked = Boolean(account?.institutionId);
      if (!linked) await api.transactions.update(transaction.id, values);
      await api.transactions.updateBudgetCategory(transaction.id, budgetCategoryId || null);
      onSaved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update transaction.");
    }
  }
  const set = (key: keyof typeof values, value: string) => setValues({ ...values, [key]: value });
  return (
    <DialogShell onClose={onClose} ariaLabelledBy="transaction-edit-title" panelClassName="max-w-lg rounded-lg bg-card p-4">
      <h2 id="transaction-edit-title" className="text-sm font-semibold">Edit transaction</h2>
      <p className="mt-1 text-xs text-muted-foreground">{account?.institutionId ? "Institution-owned details are read-only. Assign your budget category below." : "Manual and CSV transactions can be corrected."}</p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <input className={input} type="date" disabled={Boolean(account?.institutionId)} value={values.posted_at} onChange={(event) => set("posted_at", event.target.value)} />
        <input className={input} disabled={Boolean(account?.institutionId)} value={values.merchant} onChange={(event) => set("merchant", event.target.value)} />
        <select className={input} value={budgetCategoryId} onChange={(event) => setBudgetCategoryId(event.target.value)}><option value="">Provider category: {transaction.category}</option>{categories.filter((category) => category.active).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select>
        <input className={input} type="number" inputMode="decimal" disabled={Boolean(account?.institutionId)} value={values.amount} onChange={(event) => set("amount", event.target.value)} />
        <select className={input} disabled={Boolean(account?.institutionId)} value={values.type} onChange={(event) => set("type", event.target.value)}>
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
