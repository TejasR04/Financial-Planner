import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import OverviewPage from "@/app/(app)/page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/data-provider", () => ({
  useKpis: () => [], useAccountsData: () => [], useAllocationMeta: () => null,
}));
vi.mock("@/components/cash-flow-panel", () => ({ CashFlowPanel: () => null }));
vi.mock("@/components/transactions-table", () => ({ TransactionsTable: () => null }));
vi.mock("@/components/rule-based-insights", () => ({ RuleBasedInsights: () => null }));
vi.mock("@/components/charts/allocation-chart", () => ({ AllocationChart: () => null }));
vi.mock("@/components/charts/net-worth-history-chart", () => ({ NetWorthHistoryChart: () => <p>Recorded history chart</p> }));
vi.mock("@/components/charts/net-worth-chart", () => ({ NetWorthChart: () => <p>Projected chart</p> }));

afterEach(cleanup);

it("shows recorded history first and keeps projection as the second tab", () => {
  render(<OverviewPage />);
  const history = screen.getByRole("tab", { name: "History" });
  const projection = screen.getByRole("tab", { name: "Projection" });
  expect(history).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("Recorded history chart")).toBeInTheDocument();
  expect(screen.queryByText("Projected chart")).not.toBeInTheDocument();
  expect(screen.getByText(/Earlier account balances cannot be reconstructed/)).toBeInTheDocument();

  fireEvent.click(projection);
  expect(projection).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("Projected chart")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Explore assumptions" })).toBeInTheDocument();
  expect(screen.queryByText("Recorded history chart")).not.toBeInTheDocument();
});
