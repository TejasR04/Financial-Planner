import { api } from "@/lib/api-client";
import type { Account, Transaction } from "@/lib/data";

export function exportTransactionsCsv(transactions: Transaction[], filename = "meridian-transactions.csv") {
  const escape = (value: string) => `"${value.replaceAll('"', '""')}"`;
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
    .map((row) => row.map(escape).join(","))
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
      category: transaction.category,
      account: accountNames.get(transaction.account_id) ?? "Account",
      amount: Number(transaction.amount),
      type: transaction.type,
      status: transaction.status,
    })),
  );
}
