"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { api, ApiHolding } from "@/lib/api-client";
import type { Account } from "@/lib/data";

const input = "h-8 w-full rounded-md border border-border bg-background px-2.5 text-xs";

export function FinancialDetailsDialog({ account, onClose }: { account: Account | null; onClose: () => void }) {
  const debt = account?.type === "Credit" || account?.type === "Loan";
  const holdingAccount = account?.type === "Investment" || account?.type === "Retirement";
  const [values, setValues] = useState<Record<string, string>>({});
  const [holdings, setHoldings] = useState<ApiHolding[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!account) return;
    setError("");
    if (debt) api.accounts.liability(account.id).then((row) => setValues(row ? { principal: row.principal, interest_rate: String(Number(row.interest_rate) * 100), term_months: String(row.term_months), minimum_payment: row.minimum_payment, origination_date: row.origination_date } : {}));
    if (holdingAccount) api.accounts.holdings(account.id).then(setHoldings);
  }, [account, debt, holdingAccount]);
  if (!account) return null;
  const field = (name: string, placeholder: string, type = "number") => <input className={input} type={type} value={values[name] ?? ""} onChange={(e) => setValues({ ...values, [name]: e.target.value })} placeholder={placeholder} />;
  async function save() {
    try {
      if (debt) await api.accounts.saveLiability(account!.id, { principal: values.principal, interest_rate: String(Number(values.interest_rate) / 100), term_months: Number(values.term_months), minimum_payment: values.minimum_payment, origination_date: values.origination_date });
      else { const row = await api.accounts.addHolding(account!.id, { symbol: values.symbol, quantity: values.quantity, cost_basis: values.cost_basis, market_value: values.market_value, asset_class: (values.asset_class || "equity") as ApiHolding["asset_class"], as_of: values.as_of }); setHoldings([...holdings, row]); setValues({}); return; }
      onClose();
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to save details."); }
  }
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"><div className="w-full max-w-lg rounded-lg border border-border bg-card p-4 shadow-xl"><h2 className="text-sm font-semibold">{debt ? "Debt details" : "Manual holdings"} · {account.name}</h2><p className="mt-1 text-xs text-muted-foreground">{debt ? "Terms supplement the account balance; they never change net worth." : "Positions explain allocation; their values are not added again to the account balance."}</p>{holdingAccount && account.institutionId ? <p className="mt-4 text-xs text-warning">Linked holdings are managed by the institution and cannot be edited here.</p> : <div className="mt-4 grid grid-cols-2 gap-2">{debt ? <>{field("principal", "Original principal")}{field("interest_rate", "APR %")}{field("term_months", "Term months")}{field("minimum_payment", "Minimum payment")}{field("origination_date", "Origination date", "date")}</> : <>{field("symbol", "Symbol", "text")}{field("quantity", "Quantity")}{field("cost_basis", "Cost basis")}{field("market_value", "Market value")}<select className={input} value={values.asset_class ?? "equity"} onChange={(e) => setValues({ ...values, asset_class: e.target.value })}>{["equity","fixed_income","real_estate","cash","alternatives"].map((x) => <option key={x}>{x}</option>)}</select>{field("as_of", "As of", "date")}</>}</div>}{!debt && holdings.map((h) => <div key={h.id} className="mt-2 flex justify-between text-xs"><span>{h.symbol} · ${Number(h.market_value).toLocaleString()}</span>{!account.institutionId && <button className="text-destructive" onClick={async () => { await api.accounts.deleteHolding(h.id); setHoldings(holdings.filter((x) => x.id !== h.id)); }}>Remove</button>}</div>)}{error && <p className="mt-2 text-xs text-destructive">{error}</p>}<div className="mt-4 flex justify-end gap-2"><Button variant="outline" size="sm" onClick={onClose}>Close</Button>{(!holdingAccount || !account.institutionId) && <Button size="sm" onClick={() => void save()}>Save</Button>}</div></div></div>;
}
