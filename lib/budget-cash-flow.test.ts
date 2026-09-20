import { describe, expect, it } from "vitest";
import type { ApiTransaction } from "./api-client";
import { budgetCashFlowAmounts, groupBudgetCashFlowTransactions } from "./budget-cash-flow";

const row = (overrides: Partial<ApiTransaction> = {}): ApiTransaction => ({
  id: "1", account_id: "checking", account_name: "Checking", account_archived: false,
  posted_at: "2026-09-10", merchant: "Dinner", category: "dining", amount: "-120",
  type: "expense", status: "cleared", budget_category_id: "dining", budget_category_name: "Dining",
  ignored_from_budget: false, ...overrides,
});

describe("budget-based cash flow", () => {
  it("nets dining charges, refunds and both directions of categorized Zelle transfers", () => {
    const transactions = [row(), row({ id: "2", type: "transfer", merchant: "Zelle reimbursement", amount: "60" }),
      row({ id: "3", type: "transfer", merchant: "Zelle dinner", amount: "-30" }), row({ id: "4", amount: "10" })];
    expect(transactions.reduce((sum, item) => sum + budgetCashFlowAmounts(item).expenses, 0)).toBe(80);
    const groups = groupBudgetCashFlowTransactions(transactions, "outflow");
    expect(groups).toHaveLength(1);
    expect(groups[0]).toMatchObject({ name: "Dining", total: 80 });
    expect(groups[0].transactions).toHaveLength(4);
  });

  it("keeps balanced categories visible in the transaction breakdown", () => {
    const groups = groupBudgetCashFlowTransactions([row(), row({ id: "2", type: "transfer", amount: "120" })], "outflow");
    expect(groups[0].total).toBe(0);
    expect(groups[0].transactions).toHaveLength(2);
  });

  it("excludes unassigned, ignored, inactive and card-payment spending", () => {
    for (const transaction of [row({ budget_category_id: null }), row({ ignored_from_budget: true }),
      row({ type: "credit_card_payment" }), row({ category: "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT" }),
      row({ budget_category_id: "inactive" })]) {
      expect(budgetCashFlowAmounts(transaction, new Set(["dining"]))).toEqual({ income: 0, expenses: 0 });
    }
  });

  it("counts only positive classified income outside budget categories", () => {
    expect(budgetCashFlowAmounts(row({ type: "income", budget_category_id: null, amount: "4000", ignored_from_budget: true }))).toEqual({ income: 4000, expenses: 0 });
    for (const transaction of [row({ type: "transfer", budget_category_id: null, amount: "4000" }),
      row({ type: "income", budget_category_id: null, amount: "-4000" }), row({ type: "income", amount: "4000" })]) {
      expect(budgetCashFlowAmounts(transaction).income).toBe(0);
    }
  });

  it("includes pending assigned expenses and allows net reimbursements below zero", () => {
    expect(budgetCashFlowAmounts(row({ status: "pending" })).expenses).toBe(120);
    expect(budgetCashFlowAmounts(row({ type: "transfer", amount: "150" })).expenses).toBe(-150);
  });
});
