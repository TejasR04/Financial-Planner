// Isolated, tab-memory sample data. No demo request ever falls through to the server.
import type { ApiAccount, ApiTransaction, ApiBudgetCategory, ApiScenario, ApiHolding } from "@/lib/api-client";

const now = () => new Date().toISOString();
const money = (n: number) => n.toFixed(2);
const id = () => `demo-${crypto.randomUUID()}`;
function seed() {
  const accounts: ApiAccount[] = [
    ["checking", "Everyday checking", "depository", "8400"],
    ["savings", "Emergency savings", "depository", "24500"],
    ["brokerage", "Index fund portfolio", "investment", "78000"],
    ["retirement", "Workplace 401(k)", "retirement", "146000"],
    ["credit", "Rewards card", "credit", "1250"],
    ["loan", "Student loan", "loan", "18500"],
  ].map(([key, name, type, balance], i) => ({ id: key, name, type: type as ApiAccount["type"], balance, currency: "USD", mask: `${4100 + i}`, apy: type === "depository" ? "0.04" : null, status: "manual", institution: "Sample Bank", institution_id: null, institution_status: null, institution_last_synced_at: null, updated_at: now() }));
  const categories: ApiBudgetCategory[] = [["Housing", "2200"], ["Groceries", "650"], ["Dining", "350"], ["Transport", "300"], ["Utilities", "250"], ["Shopping", "300"]].map(([name, monthly_limit], i) => ({ id: `budget-${i}`, name, monthly_limit, group_name: "Living expenses", sort_order: i, active: true }));
  const transactions: ApiTransaction[] = [];
  for (let month = 0; month < 12; month++) {
    const date = new Date(); date.setDate(1); date.setMonth(date.getMonth() - month);
    const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    for (let i = 0; i < 9; i++) {
      const category = categories[i % categories.length];
      const income = i === 0;
      transactions.push({ id: `tx-${month}-${i}`, account_id: "checking", posted_at: `${monthKey}-${String(Math.min(i + 1, new Date().getDate())).padStart(2, "0")}`, merchant: income ? "Sample employer" : ["Rent", "Green Market", "Neighborhood Cafe", "Metro", "Electric company", "Home store"][i % 6], category: income ? "Income" : category.name, amount: income ? "7200" : money(-[2100, 240, 95, 120, 180, 140][i % 6]), type: income ? "income" : "expense", status: "cleared", budget_category_id: income ? null : category.id, budget_category_name: income ? null : category.name, ignored_from_budget: false, account_name: "Everyday checking", account_archived: false });
    }
  }
  const scenarios: ApiScenario[] = [
    { id: "baseline", name: "Steady growth", description: "Keep saving for retirement at 65", is_baseline: true, retirement_age: 65, savings_rate: "0.2", monthly_contribution: "1500", expected_return: "0.06", inflation_rate: "0.025", withdrawal_rate: "0.04", desired_monthly_income_today: "4000", created_at: now(), updated_at: now() },
    { id: "early", name: "Retire earlier", description: "Save more to retire at 60", is_baseline: false, retirement_age: 60, savings_rate: "0.3", monthly_contribution: "2200", expected_return: "0.06", inflation_rate: "0.025", withdrawal_rate: "0.035", desired_monthly_income_today: "4000", created_at: now(), updated_at: now() },
  ];
  const holdings: ApiHolding[] = [
    { id: "holding-1", account_id: "brokerage", symbol: "VTI", quantity: "200", cost_basis: "42000", market_value: "58000", asset_class: "equity", as_of: now().slice(0, 10) },
    { id: "holding-2", account_id: "brokerage", symbol: "BND", quantity: "270", cost_basis: "19500", market_value: "20000", asset_class: "fixed_income", as_of: now().slice(0, 10) },
    { id: "holding-3", account_id: "retirement", symbol: "VT", quantity: "1000", cost_basis: "115000", market_value: "146000", asset_class: "equity", as_of: now().slice(0, 10) },
  ];
  return { accounts, transactions, categories, scenarios, holdings, archived: [] as ApiAccount[],
    user: { id: "demo-user", full_name: "Alex Morgan", email: "alex@example.com", base_currency: "USD", date_of_birth: `${new Date().getFullYear() - 34}-03-12` },
    profile: { target_retirement_age: 65, target_equity_allocation: "0.8", default_withdrawal_rate: "0.04", include_social_security: false, expected_return: "0.06", inflation_rate: "0.025", target_savings_rate: "0.2", cash_reserve_target: "24000" },
    income: [{ id: "salary", name: "Sample salary", annual_amount: "86400", growth_rate: "0.03", active: true }],
    recommendations: [{ id: "rec-1", title: "Build your emergency reserve", body: "Keep six months of living expenses in accessible savings.", category: "Savings", impact_value: "1200", effort: "low", confidence: 0.9, status: "new", generated_at: now() }],
    rules: [] as Record<string, unknown>[], liabilities: {} as Record<string, unknown>, balanceRules: [] as Record<string, unknown>[],
  };
}
let db = seed();
export function resetDemoData() { db = seed(); }

function totals() {
  const assets = db.accounts.filter(a => !["credit", "loan"].includes(a.type)).reduce((n, a) => n + Number(a.balance), 0);
  const liabilities = db.accounts.filter(a => ["credit", "loan"].includes(a.type)).reduce((n, a) => n + Math.abs(Number(a.balance)), 0);
  return { total_assets: money(assets), total_liabilities: money(liabilities), net_worth: money(assets - liabilities) };
}
function projection(s: ApiScenario, body: Record<string, unknown>) {
  const age = Number(body.current_age ?? 34);
  let balance = Number(body.current_retirement_balance ?? 146000);
  const trajectory = Array.from({ length: Math.max(1, 96 - age) }, (_, year) => {
    const withdrawal = age + year >= s.retirement_age ? balance * Number(s.withdrawal_rate) : 0;
    const point = { year, age: age + year, balance: money(balance), withdrawal: money(withdrawal), assets: money(balance), liabilities: "0", net: money(balance) };
    balance = balance * (1 + Number(s.expected_return)) + (withdrawal ? -withdrawal : Number(s.monthly_contribution) * 12);
    return point;
  });
  const target = trajectory.find(p => p.age === s.retirement_age) ?? trajectory.at(-1)!;
  return { net_worth_at_target_age: target.balance, retirement_balance_at_target_age: target.balance, monthly_sustainable_withdrawal: money(Number(target.balance) * Number(s.withdrawal_rate) / 12), success_rate: null, trajectory, retirement_trajectory: trajectory, model_metadata: null };
}

export function demoRequest(path: string, options: RequestInit = {}): unknown {
  const url = new URL(path, "https://demo.local");
  const p = url.pathname; const q = url.searchParams;
  const method = options.method ?? "GET";
  const body = options.body ? JSON.parse(String(options.body)) : {};
  if (p.startsWith("/agent/")) throw new Error("Gemini assistant is disabled in demo mode.");
  if (p.startsWith("/plaid/") || p.endsWith("/sync")) throw new Error("Bank connections are disabled in demo mode. Add a manual sample account instead.");
  if (p === "/users/me") { if (method === "PATCH") Object.assign(db.user, body); return db.user; }
  if (p === "/users/me/planning-profile") { if (method === "PATCH") Object.assign(db.profile, body); return db.profile; }
  if (p === "/accounts/institutions") return [];
  if (p === "/accounts/archived") return db.archived;
  if (p === "/accounts/disconnected-imported-data") return { account_count: 0, transaction_count: 0, deleted: method === "DELETE" };
  if (p === "/accounts/allocation" || p === "/investments/dashboard") {
    const value = db.holdings.reduce((n, h) => n + Number(h.market_value), 0);
    const breakdown = ["equity", "fixed_income", "cash", "real_estate", "alternatives"].map(asset_class => {
      const market = db.holdings.filter(h => h.asset_class === asset_class).reduce((n, h) => n + Number(h.market_value), 0);
      return { asset_class, market_value: money(market), weight: String(value ? market / value : 0) };
    }).filter(b => Number(b.market_value));
    if (p === "/accounts/allocation") return { total_market_value: money(value), breakdown, actual_equity_allocation: breakdown.find(b => b.asset_class === "equity")?.weight ?? "0", target_equity_allocation: db.profile.target_equity_allocation, drift: "0.1", is_within_tolerance: false, rebalance_suggestions: [] };
    const cost = db.holdings.reduce((n, h) => n + Number(h.cost_basis), 0);
    const accounts = db.accounts.filter(a => ["investment", "retirement"].includes(a.type));
    return { total_value: money(accounts.reduce((n, a) => n + Number(a.balance), 0)), total_holdings_value: money(value), total_cost_basis: money(cost), total_gain_loss: money(value - cost), account_count: accounts.length, holding_count: db.holdings.length, accounts, holdings: db.holdings.map(h => ({ ...h, account_name: db.accounts.find(a => a.id === h.account_id)?.name ?? "Sample account", gain_loss: money(Number(h.market_value) - Number(h.cost_basis)) })), allocation: breakdown, history: Array.from({ length: 12 }, (_, i) => { const date = new Date(); date.setMonth(date.getMonth() - 11 + i); return { date: date.toISOString().slice(0, 10), value: money(value * (0.85 + i * 0.15 / 11)) }; }) };
  }
  const accountMatch = p.match(/^\/accounts\/([^/]+)\/(liability|holdings|balance-rules|restore|name)(?:\/([^/]+))?$/);
  if (accountMatch) {
    const [, accountId, resource, childId] = accountMatch;
    if (resource === "restore") { const row = db.archived.find(a => a.id === accountId); if (row) { db.accounts.push(row); db.archived = db.archived.filter(a => a.id !== accountId); } return row; }
    if (resource === "name") { const row = db.accounts.find(a => a.id === accountId); if (row) Object.assign(row, body); return row; }
    if (resource === "liability") { if (method === "PUT") db.liabilities[accountId] = { ...body, id: accountId, account_id: accountId }; return db.liabilities[accountId] ?? { id: accountId, account_id: accountId, principal: "18500", interest_rate: "0.045", minimum_payment: "250", term_months: 84, origination_date: null }; }
    if (resource === "holdings") { if (method === "POST") { const row = { ...body, id: id(), account_id: accountId }; db.holdings.push(row); return row; } return db.holdings.filter(h => h.account_id === accountId); }
    if (method === "DELETE") db.balanceRules = db.balanceRules.filter(r => r.id !== childId);
    if (method === "POST") { const row = { ...body, id: id(), account_id: accountId, active: true, created_at: now() }; db.balanceRules.push(row); return row; }
    return db.balanceRules.filter(r => r.account_id === accountId);
  }
  if (p === "/transactions/merchants") return [...new Set(db.transactions.map(t => t.merchant))].filter(m => m.toLowerCase().includes((q.get("search") ?? "").toLowerCase()));
  if (p.startsWith("/transactions/import/")) throw new Error("CSV import is unavailable in demo mode. You can add and edit sample transactions manually.");
  if (p === "/transactions" && method === "GET") {
    const rows = db.transactions.filter(t => (!q.get("account_id") || t.account_id === q.get("account_id")) && (!q.get("since") || t.posted_at >= q.get("since")!) && (!q.get("until") || t.posted_at <= q.get("until")!) && (!q.get("search") || t.merchant.toLowerCase().includes(q.get("search")!.toLowerCase())) && (!q.get("merchant") || t.merchant === q.get("merchant")) && (!q.get("type") || t.type === q.get("type")) && (!q.get("category") || t.category === q.get("category")) && (!q.get("budget_category_id") || t.budget_category_id === q.get("budget_category_id")) && (!q.get("direction") || (q.get("direction") === "inflow" ? Number(t.amount) > 0 : Number(t.amount) < 0)) && (q.get("cash_flow_only") !== "true" || ["income", "expense"].includes(t.type))).sort((a, b) => b.posted_at.localeCompare(a.posted_at));
    const income = rows.filter(t => t.type === "income").reduce((n, t) => n + Number(t.amount), 0);
    const spending = -rows.filter(t => t.type === "expense").reduce((n, t) => n + Number(t.amount), 0);
    const offset = Number(q.get("offset") ?? 0), limit = Number(q.get("limit") ?? 50);
    return { data: rows.slice(offset, offset + limit), total: rows.length, limit, offset, totals: { income: money(income), spending: money(spending), net_cash_flow: money(income - spending) } };
  }
  if (p === "/budgets/summary") {
    const month = (q.get("month") ?? now()).slice(0, 7);
    return { month: `${month}-01`, categories: db.categories.filter(c => c.active).map(c => { const spent = -db.transactions.filter(t => t.posted_at.startsWith(month) && t.budget_category_id === c.id && !t.ignored_from_budget && t.type === "expense").reduce((n, t) => n + Number(t.amount), 0); return { budget_category_id: c.id, name: c.name, group_name: c.group_name, budgeted: c.monthly_limit, spent: money(spent), pending: "0", remaining: money(Number(c.monthly_limit) - spent), forecast: money(spent) }; }), uncategorized: { spent: "0", pending: "0", transaction_count: 0 } };
  }
  if (p === "/budgets/review-queue") return db.transactions.filter(t => t.type === "expense" && !t.budget_category_id && !t.ignored_from_budget).map(t => ({ ...t, provider_category: t.category }));
  if (p === "/insights" || p === "/insights/generate") return [{ id: "insight-1", kind: "observation", text: "Your sample plan has a healthy emergency reserve and consistent monthly savings.", meta: "Sample insight", generated_at: now() }];
  if (p.startsWith("/financial-health")) return { overall: 82, liquidity: 90, diversification: 75, debt_ratio: 88, savings_discipline: 80, calculated_at: now() };
  if (p === "/recommendations/generate") return db.recommendations;
  if (p === "/scenarios/compare") return { rows: db.scenarios.filter(s => body.scenario_ids.includes(s.id)).map(s => ({ scenario_id: s.id, name: s.name, retirement_age: s.retirement_age, monthly_contribution: s.monthly_contribution, ...projection(s, {}), has_run: true })) };
  const scenarioMatch = p.match(/^\/scenarios\/([^/]+)\/(preview|run|runs|duplicate|sensitivity)$/);
  if (scenarioMatch) {
    const s = db.scenarios.find(s => s.id === scenarioMatch[1]); if (!s) throw new Error("Sample scenario not found.");
    if (scenarioMatch[2] === "duplicate") { const copy = { ...s, id: id(), name: `${s.name} copy`, is_baseline: false }; db.scenarios.push(copy); return copy; }
    const result = projection(s, body);
    if (scenarioMatch[2] === "sensitivity") return { baseline_balance_at_retirement: result.retirement_balance_at_target_age, baseline_success_rate: null, rows: [{ label: "Sample projection", kind: "illustration", value: result.retirement_balance_at_target_age, note: "Illustrative demo calculation" }] };
    if (scenarioMatch[2] === "runs") return { data: [] };
    return { ...result, id: id(), scenario_id: s.id, engine_version: "demo", method: "illustrative", created_at: now() };
  }
  if (p === "/simulations/retirement") {
    const years = Math.max(0, Number(body.retirement_age) - Number(body.current_age));
    let balance = Number(body.current_retirement_balance);
    for (let year = 0; year < years; year++) balance = balance * (1 + Number(body.expected_return ?? 0.06)) + Number(body.annual_contribution);
    const annual = balance * Number(body.withdrawal_rate ?? 0.04);
    return { projected_balance_at_retirement: money(balance), annual_sustainable_withdrawal: money(annual), monthly_sustainable_withdrawal: money(annual / 12), is_feasible: annual >= 48000, shortfall_or_surplus: money(annual - 48000), years_to_retirement: years };
  }
  if (p === "/simulations/net-worth") {
    const t = totals(); let assets = Number(t.total_assets);
    const series = Array.from({ length: Number(body.years ?? 30) + 1 }, (_, year_index) => { const point = { year_index, age: Number(body.current_age ?? 34) + year_index, assets: money(assets), liabilities: t.total_liabilities, net: money(assets - Number(t.total_liabilities)) }; assets = assets * (1 + Number(body.expected_return ?? 0.06)) + Number(body.annual_net_contribution ?? 18000); return point; });
    return { net_worth_today: t.net_worth, projected_net_worth_at_horizon: series.at(-1)!.net, series };
  }
  if (p === "/simulations/cash-flow") { const income = db.income.filter(i => i.active).reduce((n, i) => n + Number(i.annual_amount) / 12, 0); const expenses = db.categories.filter(c => c.active).reduce((n, c) => n + Number(c.monthly_limit), 0); return { series: Array.from({ length: body.months ?? 12 }, (_, month_index) => ({ month_index, income: money(income), expenses: money(expenses), net: money(income - expenses) })), average_monthly_surplus: money(income - expenses), projected_savings_rate: String(income ? (income - expenses) / income : 0), income_source: "Sample income", expense_source: "Sample budget" }; }
  if (p === "/simulations/debt-optimization") { const debt = db.accounts.filter(a => body.account_ids.includes(a.id)).reduce((n, a) => n + Number(a.balance), 0); return { strategy: body.strategy, months_to_debt_free: Math.ceil(debt / (250 + Number(body.extra_monthly_payment))), total_interest_paid: money(debt * 0.045), payoff_order: body.account_ids, paid_off: true, warning: "Illustrative sample estimate." }; }
  // Common local CRUD keeps all edits inside this disposable dataset.
  const collections = [
    ["/accounts", db.accounts], ["/transactions", db.transactions], ["/budgets/categories", db.categories], ["/budgets/merchant-rules", db.rules], ["/income-sources", db.income], ["/scenarios", db.scenarios], ["/recommendations", db.recommendations], ["/holdings", db.holdings],
  ] as const;
  for (const [base, typedRows] of collections) {
    if (p !== base && !p.startsWith(`${base}/`)) continue;
    const rows = typedRows as unknown as Record<string, unknown>[];
    const rowId = p.slice(base.length + 1).split("/")[0];
    const row = rows.find(r => r.id === rowId);
    if (method === "GET") {
      if (base === "/accounts") return { data: db.accounts.filter(a => !q.get("type") || a.type === q.get("type")), ...totals() };
      return rowId ? row : rows.filter(r => !q.get("status") || r.status === q.get("status"));
    }
    if (method === "DELETE") { const index = rows.findIndex(r => r.id === rowId); if (index >= 0) { if (base === "/accounts") db.archived.push({ ...db.accounts[index], ...{ archived_at: now() } }); rows.splice(index, 1); } return; }
    if (method === "PATCH" || rowId) { if (!row) throw new Error("Sample record not found."); Object.assign(row, body); if (base === "/transactions") row.budget_category_name = db.categories.find(c => c.id === row.budget_category_id)?.name ?? null; return row; }
    const defaults = base === "/accounts" ? { currency: "USD", status: "manual", mask: null, apy: null, institution: null, institution_id: null, institution_status: null, updated_at: now() } : base === "/transactions" ? { status: "cleared", budget_category_id: null, budget_category_name: null, ignored_from_budget: false, account_name: db.accounts.find(a => a.id === body.account_id)?.name, account_archived: false } : base === "/scenarios" ? { ...db.scenarios[0], is_baseline: false } : { active: true, sort_order: rows.length };
    const created = { ...defaults, ...body, id: id(), created_at: now(), updated_at: now() }; rows.push(created); return created;
  }
  throw new Error("This action is unavailable in demo mode.");
}
