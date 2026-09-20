import type { ApiTransaction } from "./api-client";
import { isCardPayment } from "./cash-flow";

type BudgetCashFlowTransaction = Pick<ApiTransaction,
  "type" | "category" | "merchant" | "amount" | "budget_category_id" | "ignored_from_budget"
>;

/** Dashboard spending follows assigned budget activity, including reimbursements. */
export function budgetCashFlowAmounts(
  transaction: BudgetCashFlowTransaction,
  activeCategoryIds?: ReadonlySet<string>,
) {
  const amount = Number(transaction.amount);
  if (!Number.isFinite(amount) || isCardPayment(transaction)) return { income: 0, expenses: 0 };
  const categorized = transaction.budget_category_id != null
    && (!activeCategoryIds || activeCategoryIds.has(transaction.budget_category_id));
  return {
    // The transaction type is authoritative for income. Older imports can
    // retain a stale budget-category assignment, but income never contributes
    // to budget spending and that stale link must not hide it from cash flow.
    income: transaction.type === "income" && amount > 0 ? amount : 0,
    expenses: categorized && !transaction.ignored_from_budget
      && (transaction.type === "expense" || transaction.type === "transfer") ? -amount : 0,
  };
}

export function groupBudgetCashFlowTransactions(
  transactions: ApiTransaction[],
  direction: "inflow" | "outflow",
  activeCategoryIds?: ReadonlySet<string>,
) {
  const groups = new Map<string, { id: string; name: string; total: number; transactions: ApiTransaction[] }>();
  for (const transaction of transactions) {
    const amounts = budgetCashFlowAmounts(transaction, activeCategoryIds);
    const value = direction === "inflow" ? amounts.income : amounts.expenses;
    if (value === 0) continue;
    const id = direction === "outflow" ? transaction.budget_category_id! : "income";
    const group = groups.get(id) ?? {
      id,
      name: direction === "outflow" ? transaction.budget_category_name ?? "Budget category" : "Income outside the budget",
      total: 0,
      transactions: [],
    };
    group.total += value;
    group.transactions.push(transaction);
    groups.set(id, group);
  }
  return [...groups.values()].sort((a, b) => a.name.localeCompare(b.name));
}
