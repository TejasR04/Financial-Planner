import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ApiTransaction } from "@/lib/api-client";
import { CashFlowDetails } from "./cash-flow-details";

const mocks = vi.hoisted(() => ({ listAll: vi.fn(), categories: vi.fn() }));
vi.mock("@/lib/api-client", () => ({ api: { transactions: { listAll: mocks.listAll }, budgets: { categories: mocks.categories } } }));
vi.mock("@/lib/data-provider", () => ({ useDataGeneration: () => 0 }));
afterEach(cleanup);

const transaction = (id: string, amount: string, type: ApiTransaction["type"], budgetCategory: string | null): ApiTransaction => ({
  id, amount, type, budget_category_id: budgetCategory, budget_category_name: budgetCategory === "dining" ? "Dining" : null,
  account_id: "checking", account_name: "Checking", account_archived: false, posted_at: "2026-09-10",
  merchant: id, category: "other", status: "cleared", ignored_from_budget: false,
});

beforeEach(() => {
  vi.clearAllMocks();
  mocks.categories.mockResolvedValue([{ id: "dining", name: "Dining", active: true }]);
  mocks.listAll.mockResolvedValue([
    transaction("Dinner with friends", "-120", "expense", "dining"),
    transaction("Zelle repayment", "120", "transfer", "dining"),
    transaction("Unassigned purchase", "-40", "expense", null),
    transaction("Paycheck", "4000", "income", null),
  ]);
});

describe("cash flow transaction breakdown", () => {
  it("shows all categorized transactions together even when the total is zero", async () => {
    render(<CashFlowDetails month="2026-09" direction="outflow" onClose={vi.fn()} />);
    expect(await screen.findByText("Net budget expenses: $0.00")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Dining" })).toBeInTheDocument();
    expect(screen.getByText("Dinner with friends")).toBeInTheDocument();
    expect(screen.getByText("Zelle repayment")).toBeInTheDocument();
    expect(screen.queryByText("Unassigned purchase")).not.toBeInTheDocument();
    expect(screen.queryByText("Paycheck")).not.toBeInTheDocument();
    expect(mocks.listAll).toHaveBeenCalledWith({ since: "2026-09-01", until: "2026-09-30" }, expect.any(AbortSignal));
  });

  it("shows only positive non-budget income when the income bar is selected", async () => {
    render(<CashFlowDetails month="2026-09" direction="inflow" onClose={vi.fn()} />);
    expect(await screen.findByText("Total income: $4,000.00")).toBeInTheDocument();
    expect(screen.getByText("Paycheck")).toBeInTheDocument();
    expect(screen.queryByText("Zelle repayment")).not.toBeInTheDocument();
  });

  it("allows a failed request to be retried", async () => {
    mocks.listAll.mockRejectedValueOnce(new Error("Connection interrupted"));
    render(<CashFlowDetails month="2026-09" direction="outflow" onClose={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Connection interrupted");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Dinner with friends")).toBeInTheDocument();
  });

  it("does not let an old month's response overwrite a newer selection", async () => {
    let finishOld!: (rows: ApiTransaction[]) => void;
    mocks.listAll.mockImplementationOnce(() => new Promise<ApiTransaction[]>((resolve) => { finishOld = resolve; }));
    const { rerender } = render(<CashFlowDetails month="2026-08" direction="outflow" onClose={vi.fn()} />);
    rerender(<CashFlowDetails month="2026-09" direction="outflow" onClose={vi.fn()} />);
    expect(await screen.findByText("Dinner with friends")).toBeInTheDocument();
    finishOld([transaction("Old month", "-10", "expense", "dining")]);
    await waitFor(() => expect(screen.queryByText("Old month")).not.toBeInTheDocument());
  });
});
