import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import BudgetPage from "@/app/(app)/budget/page";

const mocks = vi.hoisted(() => ({
  push: vi.fn(), summary: vi.fn(), categories: vi.fn(), reviewQueue: vi.fn(),
  updateClassification: vi.fn(), updateBudgetCategory: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock("@/components/charts/spending-pace-chart", () => ({ SpendingPaceChart: () => <div>Spending comparison</div> }));
vi.mock("@/components/budget-breakdown", () => ({ BudgetBreakdown: () => <div>Category breakdown</div> }));
vi.mock("@/lib/api-client", () => ({ ApiError: class extends Error {}, api: {
  budgets: mocks,
  transactions: { updateClassification: mocks.updateClassification, updateBudgetCategory: mocks.updateBudgetCategory },
} }));
vi.mock("@/lib/data-provider", () => ({ useDataRefresh: () => vi.fn() }));

describe("budget summary and review scope", () => {
  it("includes uncategorized spending and uses the review queue for review amounts", async () => {
    mocks.categories.mockResolvedValue([]);
    mocks.summary.mockResolvedValue({ categories: [{ budget_category_id: "one", name: "Dining", group_name: "Wants", budgeted: "200", spent: "100", pending: "5", remaining: "95", forecast: "210" }], uncategorized: { spent: "10", pending: "0", transaction_count: 1 } });
    mocks.reviewQueue.mockResolvedValue([{ id: "old", posted_at: "2025-01-01", merchant: "Old transaction", amount: "-45", status: "cleared", type: "expense" }]);
    render(<BudgetPage />);
    await waitFor(() => expect(screen.getByText("$115.00")).toBeInTheDocument());
    expect(screen.getByText("$45.00 posted · $0.00 pending")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review 1 transaction" })).toHaveAttribute("href", "#transaction-review");
    await userEvent.selectOptions(screen.getByLabelText("Category order"), "group");
    expect(screen.getByRole("heading", { name: "Wants" })).toBeInTheDocument();
  });

  it("changes an income transaction to an expense before assigning a budget category", async () => {
    mocks.categories.mockResolvedValue([{ id: "dining", name: "Dining", active: true }]);
    mocks.summary.mockResolvedValue({ categories: [], uncategorized: { spent: "0", pending: "0", transaction_count: 0 } });
    mocks.reviewQueue.mockResolvedValue([{ id: "income-row", posted_at: "2026-09-01", merchant: "Cafe", provider_category: "Income", amount: "-20", status: "cleared", type: "income", budget_category_id: null }]);
    mocks.updateClassification.mockResolvedValue({});
    mocks.updateBudgetCategory.mockResolvedValue({});

    render(<BudgetPage />);
    const merchant = await screen.findByText("Cafe");
    await userEvent.selectOptions(within(merchant.closest("tr")!).getByRole("combobox"), "dining");
    await userEvent.click(screen.getByRole("button", { name: "Only this transaction" }));

    await waitFor(() => expect(mocks.updateBudgetCategory).toHaveBeenCalledWith("income-row", "dining"));
    expect(mocks.updateClassification).toHaveBeenCalledWith("income-row", "expense");
    expect(mocks.updateClassification.mock.invocationCallOrder[0]).toBeLessThan(mocks.updateBudgetCategory.mock.invocationCallOrder[0]);
  });
});
