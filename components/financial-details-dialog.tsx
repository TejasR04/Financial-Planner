"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { DialogShell } from "@/components/ui/dialog-shell";
import { api, ApiHolding, ApiLoanBalanceRule } from "@/lib/api-client";
import type { Account } from "@/lib/data";

const input = "h-8 w-full rounded-md border border-border bg-background px-2.5 text-xs";

export function FinancialDetailsDialog({ account, onClose }: { account: Account | null; onClose: () => void }) {
  const debt = account?.type === "Credit" || account?.type === "Loan";
  const holdingAccount = account?.type === "Investment" || account?.type === "Retirement";
  const [values, setValues] = useState<Record<string, string>>({});
  const [holdings, setHoldings] = useState<ApiHolding[]>([]);
  const [error, setError] = useState("");
  const [rules, setRules] = useState<ApiLoanBalanceRule[]>([]);
  const [ruleMode, setRuleMode] = useState<"scheduled" | "merchant">("scheduled");
  const [ruleAmount, setRuleAmount] = useState("");
  const [ruleFrequency, setRuleFrequency] = useState<"once" | "monthly">("monthly");
  const [ruleDate, setRuleDate] = useState("");
  const [merchantPattern, setMerchantPattern] = useState("");

  const [merchantOptions, setMerchantOptions] = useState<string[]>([]);
  const [selectedMerchant, setSelectedMerchant] = useState("");
  const [merchantLoading, setMerchantLoading] = useState(false);
  const [merchantError, setMerchantError] = useState("");
  const [savingRule, setSavingRule] = useState(false);

  useEffect(() => {
    if (!account || account.institutionId || !debt || ruleMode !== "merchant" || selectedMerchant) return;
    const controller = new AbortController();
    setMerchantLoading(true);
    setMerchantError("");
    const timer = setTimeout(() => {
      api.transactions.merchants(merchantPattern, controller.signal).then(setMerchantOptions)
        .catch(() => { if (!controller.signal.aborted) setMerchantError("Couldn't load merchants. Try searching again."); })
        .finally(() => { if (!controller.signal.aborted) setMerchantLoading(false); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [account, debt, ruleMode, merchantPattern, selectedMerchant]);

  useEffect(() => {
    if (!account) return;
    setError("");
    setRules([]);
    setMerchantPattern("");
    setSelectedMerchant("");
    if (debt) {
      api.accounts.liability(account.id).then((row) => setValues(row ? {
        principal: row.principal ?? "",
        interest_rate: row.interest_rate == null ? "" : String(Number(row.interest_rate) * 100),
        term_months: row.term_months == null ? "" : String(row.term_months),
        minimum_payment: row.minimum_payment ?? "",
        origination_date: row.origination_date ?? "",
      } : {}));
      if (!account.institutionId) api.accounts.balanceRules(account.id).then(setRules).catch(() => setRules([]));
    }
    if (holdingAccount) api.accounts.holdings(account.id).then(setHoldings);
  }, [account, debt, holdingAccount]);

  if (!account) return null;
  const field = (name: string, placeholder: string, type = "number") => (
    <input className={input} type={type} value={values[name] ?? ""} onChange={(event) => setValues({ ...values, [name]: event.target.value })} placeholder={placeholder} />
  );

  async function save() {
    try {
      if (debt) {
        await api.accounts.saveLiability(account!.id, {
          principal: values.principal || null,
          interest_rate: values.interest_rate ? String(Number(values.interest_rate) / 100) : null,
          term_months: values.term_months ? Number(values.term_months) : null,
          minimum_payment: values.minimum_payment || null,
          origination_date: values.origination_date || null,
        });
      } else {
        const row = await api.accounts.addHolding(account!.id, {
          symbol: values.symbol,
          quantity: values.quantity,
          cost_basis: values.cost_basis,
          market_value: values.market_value,
          asset_class: (values.asset_class || "equity") as ApiHolding["asset_class"],
          as_of: values.as_of,
        });
        setHoldings([...holdings, row]);
        setValues({});
        return;
      }
      onClose();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save details.");
    }
  }

  async function addRule() {
    if (savingRule) return;
    setSavingRule(true);
    try {
      setError("");
      const row = await api.accounts.createBalanceRule(account!.id, ruleMode === "scheduled"
        ? { mode: "scheduled", amount: ruleAmount, frequency: ruleFrequency, next_run_date: ruleDate }
        : { mode: "merchant", merchant_pattern: selectedMerchant });
      setRules([...rules, row]);
      setRuleAmount("");
      setRuleDate("");
      setMerchantPattern("");
      setSelectedMerchant("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to add automatic payment.");
    } finally {
      setSavingRule(false);
    }
  }

  return (
    <DialogShell onClose={onClose} ariaLabelledBy="financial-details-title" panelClassName="max-w-lg rounded-lg bg-card p-4">
      <h2 id="financial-details-title" className="text-sm font-semibold">{debt ? "Debt details" : "Manual holdings"} · {account.name}</h2>
      <p className="mt-1 text-xs text-muted-foreground">{debt ? "All debt details are optional. Add only what you know; these fields do not change net worth." : "Positions explain allocation; their values are not added again to the account balance."}</p>
      {holdingAccount && account.institutionId ? (
        <p className="mt-4 text-xs text-warning">Linked holdings are managed by the institution and cannot be edited here.</p>
      ) : (
        <div className="mt-4 grid grid-cols-2 gap-2">
          {debt ? <>{field("principal", "Original principal (optional)")}<label className="relative"><input className={`${input} pr-7`} type="number" inputMode="decimal" step="0.01" value={values.interest_rate ?? ""} onChange={(event) => setValues({ ...values, interest_rate: event.target.value })} placeholder="APR (optional)" /><span className="pointer-events-none absolute right-2 top-2 text-xs text-muted-foreground">%</span></label>{field("term_months", "Term months (optional)")}{field("minimum_payment", "Minimum payment (optional)")}{field("origination_date", "Origination date", "date")}</> : <>{field("symbol", "Symbol", "text")}{field("quantity", "Quantity")}{field("cost_basis", "Cost basis")}{field("market_value", "Market value")}<select className={input} value={values.asset_class ?? "equity"} onChange={(event) => setValues({ ...values, asset_class: event.target.value })}>{["equity", "fixed_income", "real_estate", "cash", "alternatives"].map((assetClass) => <option key={assetClass}>{assetClass}</option>)}</select>{field("as_of", "As of", "date")}</>}
        </div>
      )}
      {debt && !account.institutionId && (
        <section className="mt-5 border-t border-border pt-4">
          <h3 className="text-xs font-semibold">Automatic balance reductions</h3>
          <p className="mt-1 text-xs text-muted-foreground">Reduce this balance on a schedule or when a cleared payment transaction matches a merchant.</p>
          {rules.map((rule) => (
            <div key={rule.id} className="mt-2 flex items-center justify-between rounded-md border border-border px-3 py-2 text-xs">
              <span>{rule.mode === "merchant" ? `Merchant matches “${rule.merchant_pattern}” · use transaction amount` : `${rule.frequency === "monthly" ? "Monthly" : "One time"} · $${Number(rule.amount).toFixed(2)} · next ${rule.next_run_date}`}{!rule.active ? " · completed" : ""}</span>
              <button type="button" className="text-destructive" onClick={async () => { await api.accounts.deleteBalanceRule(account.id, rule.id); setRules(rules.filter((item) => item.id !== rule.id)); }}>Remove</button>
            </div>
          ))}
          <div className="mt-3 grid grid-cols-2 gap-2">
            <select className={input} value={ruleMode} onChange={(event) => setRuleMode(event.target.value as "scheduled" | "merchant")}><option value="scheduled">Scheduled payment</option><option value="merchant">Merchant-linked payment</option></select>
            {ruleMode === "scheduled" ? <select className={input} value={ruleFrequency} onChange={(event) => setRuleFrequency(event.target.value as "once" | "monthly")}><option value="monthly">Monthly</option><option value="once">One time</option></select> : <input className={input} value={merchantPattern} onChange={(event) => { setMerchantPattern(event.target.value); setSelectedMerchant(""); }} aria-label="Search payment merchants" placeholder="Search your transaction merchants…" />}
            {ruleMode === "scheduled" && <><input className={input} type="number" inputMode="decimal" min="0.01" step="0.01" value={ruleAmount} onChange={(event) => setRuleAmount(event.target.value)} placeholder="Payment amount" /><input className={input} type="date" value={ruleDate} onChange={(event) => setRuleDate(event.target.value)} /></>}
          </div>
          {ruleMode === "merchant" && <div className="mt-2 text-xs">
            <p className="text-muted-foreground">Select a merchant from your outgoing transactions. Cleared payments dated after today will reduce this balance by the full payment amount, once per transaction. Interest is not separated.</p>
            {selectedMerchant ? <p className="mt-2">Selected: {selectedMerchant}</p> : merchantLoading ? <p className="mt-2">Searching…</p> : merchantError ? <p role="alert" className="mt-2 text-destructive">{merchantError}</p> : <ul className="mt-2 max-h-36 overflow-auto rounded border border-border">{merchantOptions.map((merchant) => <li key={merchant}><button type="button" className="w-full px-2 py-2 text-left hover:bg-muted" onClick={() => { setSelectedMerchant(merchant); setMerchantPattern(merchant); }}>{merchant}</button></li>)}{!merchantOptions.length && <li className="p-2 text-muted-foreground">No matching payment merchants.</li>}</ul>}
          </div>}
          <Button className="mt-2" variant="outline" size="sm" type="button" onClick={() => void addRule()} disabled={savingRule || (ruleMode === "scheduled" ? !ruleAmount || !ruleDate : !selectedMerchant)}>Add automatic payment</Button>
        </section>
      )}
      {!debt && holdings.map((holding) => (
        <div key={holding.id} className="mt-2 flex justify-between text-xs">
          <span>{holding.symbol} · ${Number(holding.market_value).toLocaleString()}</span>
          {!account.institutionId && <button className="text-destructive" onClick={async () => { await api.accounts.deleteHolding(holding.id); setHoldings(holdings.filter((row) => row.id !== holding.id)); }}>Remove</button>}
        </div>
      ))}
      {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onClose}>Close</Button>
        {(!holdingAccount || !account.institutionId) && <Button size="sm" onClick={() => void save()}>Save</Button>}
      </div>
    </DialogShell>
  );
}
