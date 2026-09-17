import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { ApiBudgetSummary } from "@/lib/api-client";
import { SpendingPaceChart } from "./spending-pace-chart";

vi.mock("recharts", () => ({
  ResponsiveContainer: () => null, CartesianGrid: () => null, Line: () => null, LineChart: () => null,
  ReferenceLine: () => null, Tooltip: () => null, XAxis: () => null, YAxis: () => null,
}));
afterEach(cleanup);

it("compares through the latest current day against the average, not last month", () => {
  const summary: ApiBudgetSummary = { month: "2026-09-01", categories: [], uncategorized: { spent: "0", pending: "0", transaction_count: 0 },
    daily_spending: ["100", "150", null], average_daily_spending: ["50", "100", "200"],
    previous_daily_spending: ["1000", "2000", "3000"], average_month_count: 3,
  };
  render(<SpendingPaceChart summary={summary} month="2026-09" budget={0} loading={false} />);
  expect(screen.getByText("$50.00 more")).toBeInTheDocument();
  expect(screen.getByText("than your average through day 2")).toBeInTheDocument();
  expect(screen.getByText("Average (3 completed months) — dashed")).toBeInTheDocument();
});

it("does not substitute zero or last month for missing average history", () => {
  render(<SpendingPaceChart summary={null} month="2026-09" budget={0} loading={false} />);
  expect(screen.getByText("A completed month of history is needed for comparison.")).toBeInTheDocument();
});
