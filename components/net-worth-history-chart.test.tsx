import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { NetWorthHistoryChart } from "@/components/charts/net-worth-history-chart";

const mocks = vi.hoisted(() => ({ netWorthHistory: vi.fn() }));
vi.mock("@/lib/api-client", () => ({ api: { accounts: mocks } }));
vi.mock("@/lib/data-provider", () => ({ useDataGeneration: () => 0 }));
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <>{children}</>,
  AreaChart: ({ data }: { data: { date: string; assets: number; liabilities: number; net: number }[] }) =>
    <div data-testid="recorded-net-worth-points" data-points={JSON.stringify(data)} />,
  Area: () => null, CartesianGrid: () => null, Tooltip: () => null, XAxis: () => null, YAxis: () => null,
}));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("renders dated observed totals without filling missing dates", async () => {
  mocks.netWorthHistory.mockResolvedValue([
    { date: "2026-09-26", assets: "1200", liabilities: "200", net: "1000" },
    { date: "2026-09-28", assets: "1300", liabilities: "150", net: "1150" },
  ]);
  render(<NetWorthHistoryChart />);
  const chart = await screen.findByTestId("recorded-net-worth-points");
  const points = JSON.parse(chart.getAttribute("data-points")!);
  expect(points).toHaveLength(2);
  expect(points.map((point: { date: string }) => point.date)).toEqual(["2026-09-26", "2026-09-28"]);
  expect(points[1]).toMatchObject({ assets: 1300, liabilities: 150, net: 1150 });
  expect(mocks.netWorthHistory).toHaveBeenCalledOnce();
});

it("dates the first observation and waits for a second day before drawing a line", async () => {
  mocks.netWorthHistory.mockResolvedValue([
    { date: "2026-09-28", assets: "1200", liabilities: "200", net: "1000" },
  ]);
  render(<NetWorthHistoryChart />);
  expect(await screen.findByText(/Recorded Sep 28, 2026/)).toBeInTheDocument();
  expect(screen.queryByTestId("recorded-net-worth-points")).not.toBeInTheDocument();
});
