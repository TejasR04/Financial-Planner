import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import InvestmentsPage from "@/app/(app)/investments/page";

const mocks = vi.hoisted(() => ({ dashboard: vi.fn(), holdingHistory: vi.fn() }));
vi.mock("@/lib/api-client", () => ({ ApiError: class extends Error {}, api: { investments: mocks } }));
vi.mock("@/lib/data-provider", () => ({ useDataGeneration: () => 0 }));
vi.mock("recharts", () => ({
  ResponsiveContainer: () => null, CartesianGrid: () => null, Line: () => null, LineChart: () => null,
  Tooltip: () => null, XAxis: () => null, YAxis: () => null,
}));
afterEach(cleanup);

it("shows cash without fabricated gains and explains the two valuation totals", async () => {
  mocks.dashboard.mockResolvedValue({ total_value: "11000", total_holdings_value: "10000", total_cost_basis: "0", total_gain_loss: null,
    excluded_gain_loss_value: "10000", account_count: 1, holding_count: 1, accounts: [], allocation: [], history: [],
    holdings: [{ account_id: "one", account_name: "Brokerage", symbol: "SPAXX", quantity: "10000", cost_basis: null,
      market_value: "10000", gain_loss: null, asset_class: "cash", as_of: "2026-09-17" }],
  });
  render(<InvestmentsPage />);
  const symbol = await screen.findByText("SPAXX");
  const row = symbol.closest("tr")!;
  expect(within(row).getAllByText("—")).toHaveLength(2);
  expect(within(row).queryByText("+$10,000.00")).not.toBeInTheDocument();
  expect(screen.getByText("Investment account balances")).toBeInTheDocument();
  expect(screen.getByText("Reported holdings value")).toBeInTheDocument();
  expect(screen.getByText(/do not add them together/)).toBeInTheDocument();
});

it("charts the selected account's holding and returns to the total view", async () => {
  mocks.dashboard.mockResolvedValue({ total_value: "2000", total_holdings_value: "2000", total_cost_basis: "0", total_gain_loss: null,
    account_count: 2, holding_count: 2, accounts: [], allocation: [], history: [
      { date: "2026-09-24", value: "1700" }, { date: "2026-09-25", value: "2000" },
    ], holdings: [
      { account_id: "one", account_name: "Brokerage", symbol: "VOO", quantity: "1", cost_basis: null, market_value: "900", gain_loss: null, asset_class: "equity", as_of: "2026-09-25" },
      { account_id: "two", account_name: "Retirement", symbol: "VOO", quantity: "1", cost_basis: null, market_value: "1100", gain_loss: null, asset_class: "equity", as_of: "2026-09-25" },
    ],
  });
  mocks.holdingHistory.mockResolvedValue({ account_id: "two", symbol: "VOO", history: [
    { date: "2026-09-24", value: "1000" }, { date: "2026-09-25", value: "1100" },
  ] });
  render(<InvestmentsPage />);
  expect(await screen.findByText("Investment value")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "View VOO in Retirement chart" }));
  expect(mocks.holdingHistory).toHaveBeenCalledWith("two", "VOO");
  expect(await screen.findByText("VOO value")).toBeInTheDocument();
  expect(screen.getByText("Retirement · position market value over time")).toBeInTheDocument();
  expect(screen.getByText("+$100.00 since Sep 24")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Back to total" }));
  expect(screen.getByText("Investment value")).toBeInTheDocument();
  expect(screen.getByText("All brokerage and retirement accounts · daily account balances")).toBeInTheDocument();
});
