import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import InvestmentsPage from "@/app/(app)/investments/page";

const mocks = vi.hoisted(() => ({ dashboard: vi.fn(), holdingHistory: vi.fn() }));
vi.mock("@/lib/api-client", () => ({ ApiError: class extends Error {}, api: { investments: mocks } }));
vi.mock("@/lib/data-provider", () => ({ useDataGeneration: () => 0 }));
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <>{children}</>, CartesianGrid: () => null, Line: () => null,
  LineChart: ({ data }: { data: { date: string; value: number; label: string }[] }) => <div data-testid="investment-chart-data" data-dates={data.map((point) => point.date).join("|")} data-values={data.map((point) => point.value).join("|")} data-labels={data.map((point) => point.label).join("|")} />,
  Tooltip: () => null, XAxis: () => null, YAxis: () => null,
}));
afterEach(() => {
  vi.useRealTimers();
  cleanup();
});
beforeEach(() => vi.clearAllMocks());

function dateDaysAgo(days: number) {
  const date = new Date();
  date.setDate(date.getDate() - days);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function displayDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

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
      { account_id: "one", account_name: "Brokerage", symbol: "VOO", quantity: "1", cost_basis: null, market_value: "900", gain_loss: null, asset_class: "equity", as_of: "2026-09-25", last_price: null, price_as_of: null },
      { account_id: "two", account_name: "Retirement", symbol: "VOO", quantity: "1", cost_basis: null, market_value: "1100", gain_loss: null, asset_class: "equity", as_of: "2026-09-25", last_price: null, price_as_of: null },
    ],
  });
  mocks.holdingHistory.mockResolvedValue({ account_id: "two", symbol: "VOO", last_price: "1100", price_as_of: "2026-09-25", history: [
    { date: "2026-09-24", value: "1000" }, { date: "2026-09-25", value: "1100" },
  ] });
  render(<InvestmentsPage />);
  expect(await screen.findByText("Investment value")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "View VOO in Retirement chart" }));
  expect(mocks.holdingHistory).toHaveBeenCalledWith("two", "VOO");
  expect(await screen.findByText("VOO value")).toBeInTheDocument();
  expect(screen.getByText("Retirement · position market value over time")).toBeInTheDocument();
  expect(await screen.findByText("+$100.00 since Sep 24")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Back to total" }));
  expect(screen.getByText("Investment value")).toBeInTheDocument();
  expect(screen.getByText("All brokerage and retirement accounts · daily account balances")).toBeInTheDocument();
});

it("filters daily position values by each range and displays the latest per-asset quote", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 8, 28, 12));
  const dates = [dateDaysAgo(200), dateDaysAgo(40), dateDaysAgo(20), dateDaysAgo(1), dateDaysAgo(0)];
  const today = dateDaysAgo(0);
  const yesterday = dateDaysAgo(1);
  const outsideYtdDate = dateDaysAgo(370);
  const allDates = [outsideYtdDate, ...dates];
  mocks.dashboard.mockResolvedValue({ total_value: "2700", total_holdings_value: "2600", total_cost_basis: "0", total_gain_loss: null,
    account_count: 1, holding_count: 1, accounts: [], allocation: [], history: [],
    holdings: [{ account_id: "one", account_name: "Brokerage", symbol: "VOO", quantity: "10", cost_basis: null,
      market_value: "2600", gain_loss: null, asset_class: "equity", as_of: today, last_price: "139.50", price_as_of: dateDaysAgo(2) }],
  });
  mocks.holdingHistory.mockResolvedValue({ account_id: "one", symbol: "VOO", last_price: "140.75", price_as_of: yesterday, history: allDates.map((date, index) => ({ date, value: String(2000 + index * 100) })) });

  render(<InvestmentsPage />);
  fireEvent.click(await screen.findByRole("button", { name: "View VOO in Brokerage chart" }));
  expect(await screen.findByText(`Close as of ${displayDate(yesterday)}`)).toBeInTheDocument();
  expect(screen.getByText("Latest asset price")).toBeInTheDocument();
  expect(screen.getByText("$140.75")).toBeInTheDocument();
  expect(screen.getByText("Current position value").nextElementSibling).toHaveTextContent("$2,500.00");
  expect(screen.getByTestId("investment-chart-data").getAttribute("data-values")).toBe(allDates.map((_, index) => String(2000 + index * 100)).join("|"));
  expect(screen.getByTestId("investment-chart-data").getAttribute("data-labels")).toBe(allDates.map(displayDate).join("|"));

  const rangeGroup = screen.getByRole("group", { name: "Position value history range" });
  for (const range of ["1D", "1M", "6M", "YTD", "All time"]) {
    expect(within(rangeGroup).getByRole("button", { name: range })).toBeInTheDocument();
  }

  fireEvent.click(within(rangeGroup).getByRole("button", { name: "1D" }));
  expect(within(rangeGroup).getByRole("button", { name: "1D" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByTestId("investment-chart-data").getAttribute("data-dates")).toBe(`${yesterday}|${today}`);

  fireEvent.click(within(rangeGroup).getByRole("button", { name: "1M" }));
  expect(screen.getByTestId("investment-chart-data").getAttribute("data-dates")).toBe([dateDaysAgo(20), yesterday, today].join("|"));

  fireEvent.click(within(rangeGroup).getByRole("button", { name: "6M" }));
  expect(screen.getByTestId("investment-chart-data").getAttribute("data-dates")).toBe([dateDaysAgo(40), dateDaysAgo(20), yesterday, today].join("|"));

  fireEvent.click(within(rangeGroup).getByRole("button", { name: "YTD" }));
  const ytdStart = `${new Date().getFullYear()}-01-01`;
  expect(screen.getByTestId("investment-chart-data").getAttribute("data-dates")).toBe(allDates.filter((date) => date >= ytdStart && date <= today).join("|"));

  fireEvent.click(within(rangeGroup).getByRole("button", { name: "All time" }));
  expect(screen.getByTestId("investment-chart-data").getAttribute("data-dates")).toBe(allDates.join("|"));
});

it("shows loading state while individual history is pending and dates a single daily value", async () => {
  const onlyDate = dateDaysAgo(3);
  let resolveHistory!: (history: { account_id: string; symbol: string; last_price: string | null; price_as_of: string | null; history: { date: string; value: string }[] }) => void;
  mocks.dashboard.mockResolvedValue({ total_value: "1000", total_holdings_value: "1000", total_cost_basis: "0", total_gain_loss: null,
    account_count: 1, holding_count: 1, accounts: [], allocation: [], history: [],
    holdings: [{ account_id: "one", account_name: "Brokerage", symbol: "XYZ", quantity: "5", cost_basis: null,
      market_value: "1000", gain_loss: null, asset_class: "equity", as_of: onlyDate, last_price: null, price_as_of: null }],
  });
  mocks.holdingHistory.mockImplementation(() => new Promise((resolve) => { resolveHistory = resolve; }));

  render(<InvestmentsPage />);
  fireEvent.click(await screen.findByRole("button", { name: "View XYZ in Brokerage chart" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Loading XYZ history");
  await act(async () => resolveHistory({ account_id: "one", symbol: "XYZ", last_price: null, price_as_of: null, history: [{ date: onlyDate, value: "1000" }] }));

  expect(await screen.findByText(`Recorded ${displayDate(onlyDate)}. This position's graph needs at least two dated values.`)).toBeInTheDocument();
  expect(screen.getByText("No quote is available for this position.")).toBeInTheDocument();
  expect(screen.queryByTestId("investment-chart-data")).not.toBeInTheDocument();
});
