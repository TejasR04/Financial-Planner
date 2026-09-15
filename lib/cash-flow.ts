import type { ApiTransaction } from "./api-client";

type CashFlowTransaction = Pick<ApiTransaction, "type" | "category" | "merchant" | "amount">;

export function isCardPayment(transaction: CashFlowTransaction): boolean {
  const category = transaction.category.toUpperCase();
  const merchant = transaction.merchant.toUpperCase();
  return transaction.type === "credit_card_payment"
    || category === "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"
    || merchant.includes("PAYMENT - BILT")
    || (category === "LOAN_PAYMENTS" && ["CREDIT CRD", "CREDIT CARD", "AUTOPAY PAYMENT", "AUTOMATIC PAYMENT", "PAYMENT - THANK"].some((marker) => merchant.includes(marker)));
}

/** Signed amounts preserve refunds and reversed income instead of inflating totals. */
export function cashFlowAmounts(transaction: CashFlowTransaction) {
  const amount = Number(transaction.amount);
  if (isCardPayment(transaction) || !Number.isFinite(amount)) return { income: 0, expenses: 0 };
  return {
    income: transaction.type === "income" ? amount : 0,
    expenses: transaction.type === "expense" ? -amount : 0,
  };
}
