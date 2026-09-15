import { describe, expect, it } from "vitest";
import { cashFlowAmounts } from "./cash-flow";

describe("cash-flow accounting", () => {
  const base = { merchant: "Store", category: "Shopping", type: "expense" as const };
  it("nets a refund against purchases", () => {
    const purchase = cashFlowAmounts({ ...base, amount: "-100" });
    const refund = cashFlowAmounts({ ...base, amount: "25" });
    expect(purchase.expenses + refund.expenses).toBe(75);
    expect(refund.income).toBe(0);
  });
  it("subtracts reversed income", () => {
    expect(cashFlowAmounts({ ...base, type: "income", amount: "-25" }).income).toBe(-25);
  });
  it("excludes transfers and legacy card payments", () => {
    expect(cashFlowAmounts({ ...base, type: "transfer", amount: "49" })).toEqual({ income: 0, expenses: 0 });
    expect(cashFlowAmounts({ ...base, merchant: "PAYMENT - BILT", amount: "-100" }).expenses).toBe(0);
  });
});
