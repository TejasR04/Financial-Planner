"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { DialogShell } from "@/components/ui/dialog-shell";
import { api, ApiHolding, ApiInvestmentContributionRule, ApiLoanBalanceRule } from "@/lib/api-client";
import type { Account } from "@/lib/data";
import { useDataRefresh } from "@/lib/data-provider";

const input = "h-8 w-full rounded-md border border-border bg-background px-2.5 text-xs";
const ordinal = (day: number) => `${day}${day % 10 === 1 && day % 100 !== 11 ? "st" : day % 10 === 2 && day % 100 !== 12 ? "nd" : day % 10 === 3 && day % 100 !== 13 ? "rd" : "th"}`;

export function FinancialDetailsDialog({ account, onClose }: { account: Account | null; onClose: () => void }) {
  const refresh = useDataRefresh();
  const debt = account?.type === "Credit" || account?.type === "Loan";
  const holdingAccount = account?.type === "Investment" || account?.type === "Retirement";
  const [values, setValues] = useState<Record<string, string>>({});
  const [holdings, setHoldings] = useState<ApiHolding[]>([]);
  const [updatingHoldingId, setUpdatingHoldingId] = useState<string | null>(null);
  const [cashBalance, setCashBalance] = useState("");
  const [cashIsLiquid, setCashIsLiquid] = useState(false);
  const [savingCash, setSavingCash] = useState(false);
  const [error, setError] = useState("");
  const [rules, setRules] = useState<ApiLoanBalanceRule[]>([]);
  const [contributionRules, setContributionRules] = useState<ApiInvestmentContributionRule[]>([]);
  const [contributionAmount, setContributionAmount] = useState("");
  const [contributionDay, setContributionDay] = useState("15");
  const [savingContribution, setSavingContribution] = useState(false);
  const [ruleMode, setRuleMode] = useState<"scheduled" | "merchant">("merchant");
  const [ruleAmount, setRuleAmount] = useState("");
  const [ruleFrequency, setRuleFrequency] = useState<"once" | "monthly">("monthly");
  const [ruleDate, setRuleDate] = useState("");
  const [merchantPattern, setMerchantPattern] = useState("");

  const [merchantOptions, setMerchantOptions] = useState<string[]>([]);
  const [selectedMerchant, setSelectedMerchant] = useState("");
  const [merchantLoading, setMerchantLoading] = useState(false);
  const [merchantError, setMerchantError] = useState("");
  const [savingRule, setSavingRule] = useState(false);
  const [loadedAccountId, setLoadedAccountId] = useState<string | null>(null);
  const accountIdRef = useRef<string | null>(account?.id ?? null);
  useLayoutEffect(() => { accountIdRef.current = account?.id ?? null; }, [account?.id]);

  useEffect(() => {
    if (!account || account.institutionId || !debt || ruleMode !== "merchant" || selectedMerchant) return;
    const controller = new AbortController();
    setMerchantLoading(true);
    setMerchantError("");
    const timer = setTimeout(() => {
      api.transactions.merchants(merchantPattern, controller.signal).then(setMerchantOptions)
        .catch(() => { if (!controller.signal.aborted) setMerchantError("Couldn't load merchants. Try searching again."); })
        .finally(() => { if (!controller.signal.aborted) setMerchantLoading(false); });
    }, 150);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [account, debt, ruleMode, merchantPattern, selectedMerchant]);

  useEffect(() => {
    setValues({ pricing_mode: "manual", as_of: new Date().toISOString().slice(0, 10) });
    setHoldings([]);
    setUpdatingHoldingId(null);
    setCashBalance(account?.reportedCashBalance == null ? "" : String(account.reportedCashBalance));
    setCashIsLiquid(account?.reportedCashIsLiquid ?? false);
    setSavingCash(false);
    setLoadedAccountId(null);
    if (!account) return;
    let current = true;
    setError("");
    setRules([]);
    setContributionRules([]);
    setContributionAmount("");
    setContributionDay("15");
    setSavingContribution(false);
    setSavingRule(false);
    setRuleMode("merchant");
    setMerchantPattern("");
    setSelectedMerchant("");
    if (debt) {
      api.accounts.liability(account.id).then((row) => { if (!current) return; setValues(row ? {
        principal: row.principal ?? "",
        interest_rate: row.interest_rate == null ? "" : String(Number(row.interest_rate) * 100),
        term_months: row.term_months == null ? "" : String(row.term_months),
        minimum_payment: row.minimum_payment ?? "",
        origination_date: row.origination_date ?? "",
      } : {}); setLoadedAccountId(account.id); }).catch(() => { if (current) setError("Couldn't load debt details."); });
      if (!account.institutionId) api.accounts.balanceRules(account.id).then((rows) => { if (current) setRules(rows); }).catch(() => { if (current) setRules([]); });
    }
    if (holdingAccount) {
      api.accounts.holdings(account.id).then((rows) => { if (current) { setHoldings(rows); setLoadedAccountId(account.id); } }).catch(() => { if (current) setError("Couldn't load holdings."); });
      if (!account.institutionId) api.accounts.contributionRules(account.id).then((rows) => { if (current) setContributionRules(rows); }).catch(() => { if (current) setError("Couldn't load recurring contributions."); });
    }
    return () => { current = false; };
  }, [account, debt, holdingAccount]);

  if (!account) return null;
  const field = (name: string, placeholder: string, type = "number") => (
    <input className={input} type={type} value={values[name] ?? ""} onChange={(event) => setValues({ ...values, [name]: event.target.value })} placeholder={placeholder} />
  );

  async function save() {
    const savingAccountId = account!.id;
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
          pricing_mode: (values.pricing_mode || "manual") as ApiHolding["pricing_mode"],
        });
        if (accountIdRef.current !== savingAccountId) return;
        setHoldings([...holdings, row]);
        setValues({ pricing_mode: "manual", as_of: new Date().toISOString().slice(0, 10) });
        refresh();
        return;
      }
      if (accountIdRef.current === savingAccountId) onClose();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save details.");
    }
  }

  async function addRule() {
    if (savingRule) return;
    const savingAccountId = account!.id;
    setSavingRule(true);
    try {
      setError("");
      const row = await api.accounts.createBalanceRule(account!.id, ruleMode === "scheduled"
        ? { mode: "scheduled", amount: ruleAmount, frequency: ruleFrequency, next_run_date: ruleDate }
        : { mode: "merchant", merchant_pattern: selectedMerchant });
      if (accountIdRef.current !== savingAccountId) return;
      setRules([...rules, row]);
      setRuleAmount("");
      setRuleDate("");
      setMerchantPattern("");
      setSelectedMerchant("");
      refresh();
    } catch (cause) {
      if (accountIdRef.current === savingAccountId) setError(cause instanceof Error ? cause.message : "Unable to add automatic payment.");
    } finally {
      if (accountIdRef.current === savingAccountId) setSavingRule(false);
    }
  }

  async function saveCash() {
    if (savingCash || !holdingAccount) return;
    const savingAccountId = account!.id;
    setSavingCash(true);
    setError("");
    try {
      const saved = await api.accounts.saveReportedCash(savingAccountId, {
        balance: cashBalance.trim() === "" ? null : cashBalance,
        is_liquid: cashBalance.trim() !== "" && cashIsLiquid,
      });
      if (accountIdRef.current !== savingAccountId) return;
      setCashBalance(saved.reported_cash_balance ?? "");
      setCashIsLiquid(saved.reported_cash_is_liquid);
      refresh();
    } catch (cause) {
      if (accountIdRef.current === savingAccountId) setError(cause instanceof Error ? cause.message : "Unable to save reported cash.");
    } finally {
      if (accountIdRef.current === savingAccountId) setSavingCash(false);
    }
  }

  async function setHoldingPricingMode(holding: ApiHolding, automatic: boolean) {
    const savingAccountId = account!.id;
    setUpdatingHoldingId(holding.id);
    setError("");
    try {
      const updated = await api.accounts.updateHolding(holding.id, {
        pricing_mode: automatic ? "automatic" : "manual",
      });
      if (accountIdRef.current !== savingAccountId) return;
      setHoldings((current) => current.map((row) => row.id === updated.id ? updated : row));
      refresh();
    } catch (cause) {
      if (accountIdRef.current === savingAccountId) setError(cause instanceof Error ? cause.message : "Unable to update ticker pricing.");
    } finally {
      if (accountIdRef.current === savingAccountId) setUpdatingHoldingId(null);
    }
  }

  async function addContributionRule() {
    if (savingContribution || !contributionAmount) return;
    const savingAccountId = account!.id;
    setSavingContribution(true);
    try {
      setError("");
      const row = await api.accounts.createContributionRule(account!.id, {
        amount: contributionAmount,
        day_of_month: Number(contributionDay),
      });
      if (accountIdRef.current !== savingAccountId) return;
      setContributionRules([...contributionRules, row].sort((left, right) => left.day_of_month - right.day_of_month));
      setContributionAmount("");
      refresh();
    } catch (cause) {
      if (accountIdRef.current === savingAccountId) setError(cause instanceof Error ? cause.message : "Unable to add recurring contribution.");
    } finally {
      if (accountIdRef.current === savingAccountId) setSavingContribution(false);
    }
  }

  return (
    <DialogShell onClose={onClose} ariaLabelledBy="financial-details-title" panelClassName="max-w-lg rounded-lg bg-card p-4">
      <h2 id="financial-details-title" className="text-sm font-semibold">{debt ? "Debt details" : account.institutionId ? "Investment details" : "Manual holdings"} · {account.name}</h2>
      <p className="mt-1 text-xs text-muted-foreground">{debt ? "APR on a manual loan adds daily interest to its balance when accounts refresh. Other debt details are for planning." : "Positions explain allocation. Automatic ticker updates change the account balance only by that position’s gain or loss."}</p>
      {holdingAccount && account.institutionId ? (
        <p className="mt-4 text-xs text-warning">Linked holdings are managed by the institution and cannot be edited here.</p>
      ) : (
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
          {debt ? <>{field("principal", "Original principal (optional)")}<label className="relative"><input className={`${input} pr-7`} type="number" inputMode="decimal" step="0.01" value={values.interest_rate ?? ""} onChange={(event) => setValues({ ...values, interest_rate: event.target.value })} placeholder="APR (optional)" /><span className="pointer-events-none absolute right-2 top-2 text-xs text-muted-foreground">%</span></label>{field("term_months", "Term months (optional)")}{field("minimum_payment", "Minimum payment (optional)")}{field("origination_date", "Origination date", "date")}</> : <>{field("symbol", "Ticker symbol", "text")}{field("quantity", "Quantity")}{field("cost_basis", "Total cost basis")}{field("market_value", "Total position value")}<select className={input} value={values.asset_class ?? "equity"} onChange={(event) => setValues({ ...values, asset_class: event.target.value })}>{["equity", "fixed_income", "real_estate", "cash", "alternatives"].map((assetClass) => <option key={assetClass}>{assetClass}</option>)}</select>{field("as_of", "As of", "date")}<label className="col-span-full flex items-start gap-2 rounded-md border border-border p-3 text-xs"><input className="mt-0.5" type="checkbox" checked={values.pricing_mode === "automatic"} onChange={(event) => setValues({ ...values, pricing_mode: event.target.checked ? "automatic" : "manual" })} /><span><span className="block font-medium text-foreground">Update from ticker during sync</span><span className="mt-0.5 block text-muted-foreground">Uses the latest completed market close. The total position value above is retained if pricing fails.</span></span></label></>}
        </div>
      )}
      {holdingAccount && (
        <section className="mt-5 border-t border-border pt-4">
          <h3 className="text-xs font-semibold">Cash held in this account</h3>
          <p className="mt-1 text-xs text-muted-foreground">Report the cash portion of this account balance. It is not added to the account value or shown as a position in Investments.</p>
          <label className="mt-3 block text-xs text-muted-foreground">Cash balance
            <input className={`${input} mt-1`} type="number" inputMode="decimal" min="0" step="0.01" value={cashBalance} onChange={(event) => setCashBalance(event.target.value)} placeholder="Leave blank if unknown" />
          </label>
          <label className="mt-3 flex items-start gap-2 text-xs"><input className="mt-0.5" type="checkbox" checked={cashIsLiquid} onChange={(event) => setCashIsLiquid(event.target.checked)} /><span>Count this cash as a liquid asset <span className="block text-muted-foreground">For example, brokerage cash may be available to spend, while HSA cash may be restricted.</span></span></label>
          <Button className="mt-3" variant="outline" size="sm" type="button" onClick={() => void saveCash()} disabled={savingCash}>{savingCash ? "Saving…" : "Save cash balance"}</Button>
        </section>
      )}
      {debt && !account.institutionId && (
        <section className="mt-5 border-t border-border pt-4">
          <h3 className="text-xs font-semibold">Automatic balance reductions</h3>
          <p className="mt-1 text-xs text-muted-foreground">Find a merchant from your transactions and select the exact result to link its future cleared payments to this loan.</p>
          {rules.map((rule) => (
            <div key={rule.id} className="mt-2 flex items-center justify-between rounded-md border border-border px-3 py-2 text-xs">
              <span>{rule.mode === "merchant" ? `Merchant matches “${rule.merchant_pattern}” · use transaction amount` : `${rule.frequency === "monthly" ? "Monthly" : "One time"} · $${Number(rule.amount).toFixed(2)} · next ${rule.next_run_date}`}{!rule.active ? " · completed" : ""}</span>
              <button type="button" className="text-destructive" onClick={async () => { await api.accounts.deleteBalanceRule(account.id, rule.id); setRules(rules.filter((item) => item.id !== rule.id)); }}>Remove</button>
            </div>
          ))}
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
            <select className={input} value={ruleMode} onChange={(event) => setRuleMode(event.target.value as "scheduled" | "merchant")}><option value="scheduled">Scheduled payment</option><option value="merchant">Merchant-linked payment</option></select>
            {ruleMode === "scheduled" ? <select className={input} value={ruleFrequency} onChange={(event) => setRuleFrequency(event.target.value as "once" | "monthly")}><option value="monthly">Monthly</option><option value="once">One time</option></select> : <label className="text-xs text-muted-foreground">Search transaction merchants<input className={`${input} mt-1`} value={merchantPattern} onChange={(event) => { setMerchantPattern(event.target.value); setSelectedMerchant(""); }} aria-label="Search payment merchants" autoComplete="off" placeholder="Type a merchant name…" /></label>}
            {ruleMode === "scheduled" && <><input className={input} type="number" inputMode="decimal" min="0.01" step="0.01" value={ruleAmount} onChange={(event) => setRuleAmount(event.target.value)} placeholder="Payment amount" /><input className={input} type="date" value={ruleDate} onChange={(event) => setRuleDate(event.target.value)} /></>}
          </div>
          {ruleMode === "merchant" && <div className="mt-2 text-xs">
            <p className="text-muted-foreground">Select a merchant from your outgoing transactions. Cleared payments dated on or after the rule is added reduce this balance by the full payment amount, once per transaction. Interest is added separately from the saved APR.</p>
            {selectedMerchant ? <p className="mt-2 rounded border border-border bg-muted px-2 py-2" role="status">Selected transaction merchant: <strong>{selectedMerchant}</strong>. Payments with matching merchant words will update this loan.</p> : merchantLoading ? <p className="mt-2">Searching transactions…</p> : merchantError ? <p role="alert" className="mt-2 text-destructive">{merchantError}</p> : <ul className="mt-2 max-h-36 overflow-auto rounded border border-border" aria-label="Matching transaction merchants">{merchantOptions.map((merchant) => <li key={merchant}><button type="button" className="w-full px-2 py-2 text-left hover:bg-muted focus:bg-muted" onClick={() => { setSelectedMerchant(merchant); setMerchantPattern(merchant); }}>{merchant}</button></li>)}{!merchantOptions.length && <li className="p-2 text-muted-foreground">No matching outgoing transaction merchants.</li>}</ul>}
          </div>}
          <Button className="mt-2" variant="outline" size="sm" type="button" onClick={() => void addRule()} disabled={savingRule || (ruleMode === "scheduled" ? !ruleAmount || !ruleDate : !selectedMerchant)}>Add automatic payment</Button>
        </section>
      )}
      {!debt && holdings.map((holding) => (
        <div key={holding.id} className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs">
          <span>{holding.symbol} · ${Number(holding.market_value).toLocaleString()} {holding.pricing_mode === "automatic" ? `· automatic${holding.last_price ? ` at $${Number(holding.last_price).toLocaleString()} as of ${holding.as_of}` : " · awaiting next completed close"}` : "· manual"}</span>
          {!account.institutionId && <div className="flex items-center gap-3"><label className="flex items-center gap-1"><input type="checkbox" aria-label={`Update ${holding.symbol} from ticker during sync`} checked={holding.pricing_mode === "automatic"} disabled={updatingHoldingId === holding.id} onChange={(event) => void setHoldingPricingMode(holding, event.target.checked)} />Auto update</label><button className="text-destructive" onClick={async () => { await api.accounts.deleteHolding(holding.id); setHoldings(holdings.filter((row) => row.id !== holding.id)); refresh(); }}>Remove</button></div>}
        </div>
      ))}
      {holdingAccount && !account.institutionId && (
        <section className="mt-5 border-t border-border pt-4">
          <h3 className="text-xs font-semibold">Recurring account contributions</h3>
          <p className="mt-1 text-xs text-muted-foreground">Add a fixed amount to this account balance every month. This tracks incoming contributions; it does not buy shares or change a holding’s quantity or cost basis.</p>
          {contributionRules.map((rule) => (
            <div key={rule.id} className="mt-2 flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-xs">
              <span>${Number(rule.amount).toFixed(2)} on the {ordinal(rule.day_of_month)} · next {rule.next_run_date}</span>
              <button type="button" className="text-destructive" onClick={async () => { await api.accounts.deleteContributionRule(account.id, rule.id); setContributionRules(contributionRules.filter((item) => item.id !== rule.id)); }}>Remove</button>
            </div>
          ))}
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            <input aria-label="Contribution amount" className={input} type="number" inputMode="decimal" min="0.01" step="0.01" value={contributionAmount} onChange={(event) => setContributionAmount(event.target.value)} placeholder="Contribution amount" />
            <select aria-label="Contribution day" className={input} value={contributionDay} onChange={(event) => setContributionDay(event.target.value)}>
              {Array.from({ length: 31 }, (_, index) => index + 1).map((day) => <option key={day} value={day}>{ordinal(day)} of each month</option>)}
            </select>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">For two monthly contributions, add two rules. Dates such as the 30th or 31st run on the final day of shorter months.</p>
          <Button className="mt-2" variant="outline" size="sm" type="button" onClick={() => void addContributionRule()} disabled={savingContribution || !contributionAmount}>{savingContribution ? "Adding…" : "Add recurring contribution"}</Button>
        </section>
      )}
      {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onClose}>Close</Button>
        {(!holdingAccount || !account.institutionId) && <Button size="sm" disabled={loadedAccountId !== account.id} onClick={() => void save()}>{loadedAccountId === account.id ? "Save" : "Loading…"}</Button>}
      </div>
    </DialogShell>
  );
}
