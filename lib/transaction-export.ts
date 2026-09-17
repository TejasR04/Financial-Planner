import { api } from "@/lib/api-client";
import type { Account, Transaction } from "@/lib/data";

export function escapeCsvCell(value: string, neutralizeFormula = true) {
  // Spreadsheet programs may execute formulas even when a CSV cell is quoted.
  // Prefix text whose first visible character is formula-capable; leading
  // whitespace and control characters must not bypass the check.
  const safeValue = neutralizeFormula && /^[\s\u0000-\u001f]*[=+\-@]/u.test(value) ? `'${value}` : value;
  return `"${safeValue.replaceAll('"', '""')}"`;
}

export function exportTransactionsCsv(transactions: Transaction[], filename = "meridian-transactions.csv") {
  const rows = transactions.map((transaction) => [
    transaction.postedAt,
    transaction.merchant,
    transaction.category,
    transaction.account,
    transaction.type,
    transaction.status,
    transaction.amount.toString(),
  ]);
  const csv = [["Date", "Merchant", "Category", "Account", "Type", "Status", "Amount"], ...rows]
    .map((row) => row.map((value, index) => escapeCsvCell(value, index !== 6)).join(","))
    .join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export async function exportAllTransactionsCsv(accounts: Pick<Account, "id" | "name">[]) {
  const accountNames = new Map(accounts.map((account) => [account.id, account.name]));
  const transactions = await api.transactions.listAll();
  exportTransactionsCsv(
    transactions.map((transaction) => ({
      id: transaction.id,
      postedAt: transaction.posted_at,
      date: transaction.posted_at,
      merchant: transaction.merchant,
      category: transaction.budget_category_name ?? transaction.category,
      account: accountNames.get(transaction.account_id) ?? "Account",
      amount: Number(transaction.amount),
      type: transaction.type,
      status: transaction.status,
    })),
  );
}
