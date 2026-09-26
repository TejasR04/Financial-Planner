import type { ApiAccount } from "@/lib/api-client";

/** Invested accounts can fund retirement regardless of their tax treatment. */
export function retirementPortfolioBalance(accounts: Pick<ApiAccount, "type" | "balance">[]): number {
  return Math.max(0, accounts
    .filter((account) => account.type === "investment" || account.type === "retirement")
    .reduce((balance, account) => balance + Number(account.balance), 0));
}
