import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import BudgetPage from "@/app/(app)/budget/page";

const mocks = vi.hoisted(() => ({ push: vi.fn(), summary: vi.fn(), categories: vi.fn(), reviewQueue: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock("@/components/charts/spending-pace-chart", () => ({ SpendingPaceChart: () => <div>Spending comparison</div> }));
vi.mock("@/components/budget-breakdown", () => ({ BudgetBreakdown: () => <div>Category breakdown</div> }));
vi.mock("@/lib/api-client", () => ({ ApiError: class extends Error {}, api: { budgets: mocks } }));
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
});
