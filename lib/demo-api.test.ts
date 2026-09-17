import { afterEach, describe, expect, it, vi } from "vitest";
import { api, setAuthToken, setDemoMode } from "./api-client";

afterEach(() => { setDemoMode(false); setAuthToken(null); vi.restoreAllMocks(); });
describe("isolated demo API", () => {
  it("supports edits and derived budgets without any backend requests", async () => {
    const network = vi.spyOn(globalThis, "fetch");
    setDemoMode(true);
    const accounts = await api.accounts.list();
    expect(accounts.data.length).toBeGreaterThan(3);
    await api.accounts.rename(accounts.data[0].id, "My sample checking");
    expect((await api.accounts.list()).data[0].name).toBe("My sample checking");
    const category = (await api.budgets.categories())[0];
    await api.budgets.updateCategory(category.id, { monthly_limit: "3000" });
    const month = new Date().toISOString().slice(0, 7);
    expect((await api.budgets.summary(month)).categories[0].budgeted).toBe("3000");
    const transaction = await api.transactions.create({ account_id: accounts.data[0].id, posted_at: `${month}-01`, merchant: "Demo purchase", category: "Shopping", amount: "-25", type: "expense" });
    expect((await api.transactions.list({ search: "Demo purchase" })).data[0].id).toBe(transaction.id);
    await api.transactions.delete(transaction.id);
    expect((await api.transactions.list({ search: "Demo purchase" })).total).toBe(0);
    expect(network).not.toHaveBeenCalled();
  });
  it("blocks Gemini and bank linking at the API boundary", async () => {
    const network = vi.spyOn(globalThis, "fetch"); setDemoMode(true);
    await expect(api.agent.chat("Hello")).rejects.toThrow("disabled in demo");
    await expect(api.agent.history()).rejects.toThrow("disabled in demo");
    await expect(api.plaid.createLinkToken()).rejects.toThrow("disabled in demo");
    expect(network).not.toHaveBeenCalled();
  });
  it("preserves signed-in credentials, clears caches, and resets sample edits on exit", async () => {
    const network = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ data: [{ id: "real" }] }), { status: 200 }));
    setAuthToken("real-session"); setDemoMode(true);
    await api.accounts.rename("checking", "Changed");
    setDemoMode(false);
    expect((await api.accounts.list()).data[0].id).toBe("real");
    expect(new Headers(network.mock.calls[0][1]?.headers).get("Authorization")).toBe("Bearer real-session");
    setDemoMode(true);
    expect((await api.accounts.list()).data[0].name).toBe("Everyday checking");
  });
  it("provides populated investments and interactive scenario projections", async () => {
    setDemoMode(true);
    expect((await api.investments.dashboard()).holdings.length).toBeGreaterThan(0);
    const params = { current_age: 34, current_retirement_balance: "146000" };
    const before = await api.scenarios.preview("baseline", params);
    await api.scenarios.update("baseline", { monthly_contribution: "3000" });
    const after = await api.scenarios.preview("baseline", params);
    expect(Number(after.net_worth_at_target_age)).toBeGreaterThan(Number(before.net_worth_at_target_age));
  });

  it("uses completed sample months for spending averages and outlooks", async () => {
    setDemoMode(true);
    const month = new Date().toISOString().slice(0, 7);
    const summary = await api.budgets.summary(month);
    expect(summary.average_month_count).toBeGreaterThan(0);
    expect(summary.average_daily_spending?.some(value => Number(value) > 0)).toBe(true);
    const before = await api.simulations.cashFlow(6);
    await api.transactions.create({ account_id: "checking", posted_at: `${month}-01`, merchant: "Big current purchase", category: "Shopping", amount: "-99999", type: "expense" });
    expect((await api.simulations.cashFlow(6)).series).toEqual(before.series);
    expect(before.series[0].month_index).toBe(1);
  });
});
