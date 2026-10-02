import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import InvestmentsPage from "@/app/(app)/investments/page";

const mocks = vi.hoisted(() => ({ dashboard: vi.fn(), holdingHistory: vi.fn(), accountHistory: vi.fn() }));
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

it("applies ranges to total investments and compares 1D with the prior recorded day", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 8, 28, 12));
  mocks.dashboard.mockResolvedValue({ total_value: "1100", total_holdings_value: "0", total_cost_basis: "0", total_gain_loss: null,
    account_count: 1, holding_count: 0, accounts: [], allocation: [], holdings: [], history: [
      { date: "2026-08-20", value: "800" },
      { date: "2026-09-25", value: "1000" },
      { date: "2026-09-28", value: "1100" },
    ],
  });
  render(<InvestmentsPage />);
  expect(await screen.findByTestId("investment-chart-data")).toHaveAttribute("data-dates", "2026-08-20|2026-09-25|2026-09-28");
  expect(screen.queryByText("Latest asset price")).not.toBeInTheDocument();
  const ranges = screen.getByRole("group", { name: "Investment value history range" });
  fireEvent.click(within(ranges).getByRole("button", { name: "1D" }));
  expect(screen.getByTestId("investment-chart-data")).toHaveAttribute("data-dates", "2026-09-25|2026-09-28");
  expect(screen.getByText("+$100.00 since Sep 25")).toBeInTheDocument();
  fireEvent.click(within(ranges).getByRole("button", { name: "1M" }));
  expect(screen.getByTestId("investment-chart-data")).toHaveAttribute("data-dates", "2026-09-25|2026-09-28");
  fireEvent.click(within(ranges).getByRole("button", { name: "All time" }));
  expect(screen.getByTestId("investment-chart-data")).toHaveAttribute("data-dates", "2026-08-20|2026-09-25|2026-09-28");
});

it("places the asset price and change together on the right", async () => {
  mocks.dashboard.mockResolvedValue({ total_value: "1100", total_holdings_value: "1100", total_cost_basis: "0", total_gain_loss: null,
    account_count: 1, holding_count: 1, accounts: [], allocation: [], history: [],
    holdings: [{ account_id: "one", account_name: "Brokerage", symbol: "VOO", quantity: "2", cost_basis: null,
      market_value: "1100", gain_loss: null, asset_class: "equity", as_of: "2026-09-25", last_price: "550", price_as_of: "2026-09-25" }],
  });
  mocks.holdingHistory.mockResolvedValue({ account_id: "one", symbol: "VOO", last_price: "550", price_as_of: "2026-09-25", history: [
    { date: "2026-09-24", value: "1000" }, { date: "2026-09-25", value: "1100" },
  ] });
  render(<InvestmentsPage />);
  fireEvent.click(await screen.findByRole("button", { name: "View VOO in Brokerage chart" }));
  const price = await screen.findByText("Latest asset price");
  const change = await screen.findByText("+$100.00 since Sep 24");
  expect(price.parentElement?.parentElement).toBe(change.parentElement);
  expect(price.parentElement?.parentElement).toHaveClass("ml-auto", "text-right");
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
  expect(await screen.findByText(`Price as of ${displayDate(yesterday)}`)).toBeInTheDocument();
  expect(screen.getByText("Latest asset price")).toBeInTheDocument();
  expect(screen.getByText("$140.75")).toBeInTheDocument();
  expect(screen.getByText("Current position value").nextElementSibling).toHaveTextContent("$2,500.00");
  fireEvent.click(screen.getByRole("button", { name: "All time" }));
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
  expect(screen.getByText("No price is available for this position.")).toBeInTheDocument();
  expect(screen.queryByTestId("investment-chart-data")).not.toBeInTheDocument();
});

it("groups holdings by account, toggles charts, preserves ranges, and resets on remount", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 8, 28, 12));
  mocks.dashboard.mockResolvedValue({ total_value: "3000", total_holdings_value: "3000", total_cost_basis: "0", total_gain_loss: null,
    account_count: 2, holding_count: 2, accounts: [
      { id: "one", name: "Brokerage", balance: "1000", type: "investment", institution: null, updated_at: null },
      { id: "two", name: "Retirement", balance: "2000", type: "retirement", institution: null, updated_at: null },
    ], allocation: [], history: [{ date: "2026-09-25", value: "2700" }, { date: "2026-09-28", value: "3000" }],
    holdings: [
      { account_id: "two", account_name: "Retirement", symbol: "VOO", quantity: "2", cost_basis: null, market_value: "2000", gain_loss: null, asset_class: "equity", as_of: "2026-09-28" },
      { account_id: "one", account_name: "Brokerage", symbol: "VTI", quantity: "1", cost_basis: null, market_value: "1000", gain_loss: null, asset_class: "equity", as_of: "2026-09-28" },
    ],
  });
  mocks.accountHistory.mockResolvedValue({ account_id: "two", history: [{ date: "2026-09-25", value: "1800" }, { date: "2026-09-28", value: "2000" }] });
  mocks.holdingHistory.mockResolvedValue({ account_id: "two", symbol: "VOO", last_price: null, price_as_of: null, history: [{ date: "2026-09-25", value: "1800" }, { date: "2026-09-28", value: "2000" }] });
  const view = render(<InvestmentsPage />);
  await screen.findByRole("button", { name: "View Retirement account chart" });
  const rows = screen.getByRole("table").querySelectorAll("tbody tr");
  expect(Array.from(rows).map((row) => row.textContent)).toEqual([
    expect.stringContaining("Brokerage"), expect.stringContaining("VTI"), expect.stringContaining("Retirement"), expect.stringContaining("VOO"),
  ]);
  expect(screen.getByRole("button", { name: "YTD" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "1D" }));
  fireEvent.click(screen.getByRole("button", { name: "View Retirement account chart" }));
  expect(await screen.findByText("Retirement value")).toBeInTheDocument();
  expect(mocks.accountHistory).toHaveBeenCalledWith("two");
  expect(await screen.findByTestId("investment-chart-data")).toHaveAttribute("data-values", "1800|2000");
  expect(screen.queryByText("Latest asset price")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "1D" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "View Retirement account chart" }));
  expect(screen.getByText("Investment value")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "View VOO in Retirement chart" }));
  await screen.findByTestId("investment-chart-data");
  expect(screen.getByRole("button", { name: "1D" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "View VOO in Retirement chart" }));
  expect(screen.getByText("Investment value")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "1D" })).toHaveAttribute("aria-pressed", "true");
  view.unmount();
  render(<InvestmentsPage />);
  await screen.findByRole("button", { name: "View Retirement account chart" });
  expect(screen.getByRole("button", { name: "YTD" })).toHaveAttribute("aria-pressed", "true");
});
