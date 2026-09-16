import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import TransactionsPage from "@/app/(app)/transactions/page";

const mocks = vi.hoisted(() => ({ list: vi.fn(), categories: vi.fn(), refresh: vi.fn(), accounts: [], updateBudgetCategory: vi.fn(), markReviewed: vi.fn() }));
vi.mock("@/lib/data-provider", () => ({ useAccountsData: () => mocks.accounts, useDataRefresh: () => mocks.refresh }));
vi.mock("@/lib/api-client", () => ({ ApiError: class extends Error {}, api: { transactions: mocks, budgets: mocks } }));
vi.mock("@/components/transaction-entry-dialog", () => ({ TransactionEntryDialog: () => null }));
vi.mock("@/components/transaction-edit-dialog", () => ({ TransactionEditDialog: () => null }));

describe("transaction ledger", () => {
  it("uses totals for all matches and preserves exclusions when assigning a category", async () => {
    mocks.categories.mockResolvedValue([{ id: "food", name: "Food", active: true }]);
    mocks.list.mockResolvedValue({ data: [{ id: "one", account_id: "a", merchant: "Cafe", amount: "-10", posted_at: "2026-09-01", type: "expense", status: "cleared", budget_category_id: null, budget_category_name: null, ignored_from_budget: true }], total: 51, totals: { income: "25", spending: "500", net_cash_flow: "-475" } });
    mocks.updateBudgetCategory.mockResolvedValue({});
    render(<TransactionsPage />);
    await waitFor(() => expect(screen.getByText("$500.00")).toBeInTheDocument());
    const now = new Date();
    const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
    expect(mocks.list).toHaveBeenCalledWith(expect.objectContaining({ since: `${month}-01`, until: `${month}-${new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()}` }), expect.any(AbortSignal));
    expect(screen.queryByText("Net movement")).not.toBeInTheDocument();
    expect(screen.getByText("Net cash flow")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Category for Cafe" })).not.toBeInTheDocument();
    expect(screen.getByText("Excluded from budget")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Edit category for Cafe" }));
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Category for Cafe" }), "food");
    await userEvent.click(screen.getByRole("button", { name: "Only this transaction" }));
    await waitFor(() => expect(mocks.updateBudgetCategory).toHaveBeenCalledWith("one", "food"));
    expect(mocks.list).toHaveBeenCalledWith(expect.objectContaining({ includeTotals: true }), expect.any(AbortSignal));
    await userEvent.click(screen.getByRole("button", { name: "Previous month" }));
    const previous = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith(expect.objectContaining({ since: `${previous.getFullYear()}-${String(previous.getMonth() + 1).padStart(2, "0")}-01`, offset: 0 }), expect.any(AbortSignal)));
  });
});
