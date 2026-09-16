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
  const [ignoredFromBudget, setIgnoredFromBudget] = useState(transaction.ignored_from_budget);
  const categoryEligible = values.type === "expense" || values.type === "transfer";
  const [error, setError] = useState("");
  const [loadingCategories, setLoadingCategories] = useState(true);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  useEffect(() => {
    void api.budgets.categories()
      .then(setCategories)
      .catch(() => setError("Unable to load your budget categories."))
      .finally(() => setLoadingCategories(false));
  }, []);
  async function save() {
    setSaving(true);
    setError("");
    try {
      const linked = Boolean(account?.institutionId);
      if (!linked) await api.transactions.update(transaction.id, values);
      else if (values.type !== transaction.type) await api.transactions.updateClassification(transaction.id, values.type);
      await api.transactions.updateBudgetCategory(transaction.id, categoryEligible ? budgetCategoryId || null : null, categoryEligible && ignoredFromBudget);
      onSaved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update transaction.");
    } finally {
      setSaving(false);
    }
  }
  async function remove() {
    setSaving(true);
    setError("");
    try {
      await api.transactions.delete(transaction.id);
      onSaved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to delete transaction.");
      setConfirmDelete(false);
    } finally {
      setSaving(false);
    }
  }
  const set = (key: keyof typeof values, value: string) => setValues({ ...values, [key]: value });
  return (
    <DialogShell onClose={onClose} closeDisabled={saving} ariaLabelledBy="transaction-edit-title" panelClassName="max-w-lg rounded-lg bg-card p-4">
      <h2 id="transaction-edit-title" className="text-sm font-semibold">Edit transaction</h2>
      <p className="mt-1 text-xs text-muted-foreground">{account?.institutionId ? "Bank-provided date, merchant, and amount are read-only. You can change the type and budget treatment." : "Manual and CSV transactions can be corrected."}</p>
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="text-xs font-medium text-muted-foreground">Date<input aria-label="Transaction date" className={`${input} mt-1`} type="date" disabled={Boolean(account?.institutionId)} value={values.posted_at} onChange={(event) => set("posted_at", event.target.value)} /></label>
        <label className="text-xs font-medium text-muted-foreground">Merchant<input aria-label="Merchant" className={`${input} mt-1`} disabled={Boolean(account?.institutionId)} value={values.merchant} onChange={(event) => set("merchant", event.target.value)} /></label>
        <label className="col-span-2 text-xs font-medium text-muted-foreground">Budget category<select aria-label="Your budget category" className={`${input} mt-1`} disabled={loadingCategories || !categoryEligible || saving} value={categoryEligible ? budgetCategoryId : ""} onChange={(event) => setBudgetCategoryId(event.target.value)}><option value="">{categoryEligible ? "Uncategorized" : "Not included in budget"}</option>{categories.filter((category) => category.active).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
        <label className="text-xs font-medium text-muted-foreground">Amount<input aria-label="Amount" className={`${input} mt-1`} type="number" inputMode="decimal" disabled={Boolean(account?.institutionId)} value={values.amount} onChange={(event) => set("amount", event.target.value)} /></label>
        <label className="text-xs font-medium text-muted-foreground">Transaction type<select aria-label="Transaction type" className={`${input} mt-1`} disabled={saving} value={values.type} onChange={(event) => set("type", event.target.value)}>
          {["expense", "income", "transfer", "credit_card_payment", "contribution"].map((type) => <option key={type} value={type}>{type === "credit_card_payment" ? "Credit card payment" : type}</option>)}
        </select></label>
        <div className="col-span-2 rounded-md bg-muted/40 p-3 text-xs text-muted-foreground">
          <p>{values.type === "expense" ? "Expenses count in cash flow. Positive expense amounts are refunds and reduce spending." : values.type === "transfer" ? "Assign a category to include this transfer in your budget: outgoing adds spending; incoming reimburses it. Leave transfers between your own accounts uncategorized to avoid counting them as spending. Transfers remain excluded from cash flow." : values.type === "income" ? "Income counts in cash flow and is excluded from budget spending." : "Card payments and investment contributions are excluded from income and expense reporting."}</p>
          {categoryEligible && <label className="mt-3 flex items-center gap-2"><input type="checkbox" checked={ignoredFromBudget} disabled={saving} onChange={(event) => setIgnoredFromBudget(event.target.checked)} />Exclude from budget</label>}
        </div>
      </div>
      {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
      <div className="mt-4 flex items-center justify-between gap-2">
        {confirmDelete ? <div className="flex items-center gap-2"><span className="text-xs text-destructive">Delete this transaction everywhere in Meridian?</span><Button variant="destructive" size="sm" onClick={() => void remove()} disabled={saving}>{saving ? "Deleting…" : "Confirm delete"}</Button><Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)} disabled={saving}>Keep</Button></div> : <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setConfirmDelete(true)} disabled={saving}>Delete transaction</Button>}
        <div className="flex gap-2"><Button variant="outline" size="sm" onClick={onClose} disabled={saving}>Cancel</Button>
        <Button size="sm" onClick={() => void save()} disabled={saving || loadingCategories}>{saving ? "Saving…" : "Save"}</Button></div>
      </div>
    </DialogShell>
  );
}
