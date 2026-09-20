import { describe, expect, it } from "vitest";
import type { ApiTransaction } from "@/lib/api-client";
import {
  ageFromBirthDate,
  buildCashflowSeries,
  monthKey,
  twelveMonthWindow,
} from "@/lib/dashboard-data-helpers";

function transaction(overrides: Partial<ApiTransaction>): ApiTransaction {
  return {
    id: "transaction-1",
    account_id: "account-1",
    posted_at: "2026-02-10",
    merchant: "Merchant",
    category: "Category",
    amount: "0",
    type: "expense",
    status: "cleared",
    budget_category_id: null,
    budget_category_name: null,
    ignored_from_budget: false,
    account_name: "Checking",
    account_archived: false,
    ...overrides,
  };
}

describe("dashboard date helpers", () => {
  it("calculates age on either side of the birthday", () => {
    expect(ageFromBirthDate("1990-09-17T00:00:00", new Date(2026, 8, 16))).toBe(35);
    expect(ageFromBirthDate("1990-09-17T00:00:00", new Date(2026, 8, 17))).toBe(36);
    expect(ageFromBirthDate(null, new Date(2026, 8, 17))).toBeNull();
  });

  it("builds an inclusive twelve-month local calendar window", () => {
    const window = twelveMonthWindow(new Date(2026, 8, 17));

    expect(window.startDate).toBe("2025-10-01");
    expect(monthKey(window.start)).toBe("2025-10");
    expect(monthKey(window.end)).toBe("2026-09");
    expect(window.end.getDate()).toBe(30);
  });
});

describe("dashboard cash-flow series", () => {
  it("buckets signed cash flow and marks availability and the current month", () => {
    const series = buildCashflowSeries(
      [
        transaction({ posted_at: "2026-02-10", type: "income", amount: "2000" }),
        transaction({ id: "transaction-2", posted_at: "2026-02-11", amount: "-600", budget_category_id: "dining" }),
        transaction({ id: "transaction-3", posted_at: "2026-03-02", amount: "-100", budget_category_id: "dining" }),
      ],
      new Date(2026, 0, 1),
      new Date(2026, 2, 31),
      new Date(2026, 2, 15),
    );

    expect(series.map(({ monthKey: key, available, incomplete, income, expenses }) => ({
      key, available, incomplete, income, expenses,
    }))).toEqual([
      { key: "2026-01", available: false, incomplete: false, income: 0, expenses: 0 },
      { key: "2026-02", available: true, incomplete: false, income: 2000, expenses: 600 },
      { key: "2026-03", available: true, incomplete: true, income: 0, expenses: 100 },
    ]);
    expect(series[1].partialHistory).toBe(true);
  });

  it("ignores transactions outside the requested window", () => {
    const series = buildCashflowSeries(
      [transaction({ posted_at: "2025-12-31", amount: "-50" })],
      new Date(2026, 0, 1),
      new Date(2026, 0, 31),
      new Date(2026, 0, 15),
    );

    expect(series[0]).toMatchObject({ income: 0, expenses: 0 });
  });

  it("uses known history before the bounded query and includes categorized transfer offsets", () => {
    const series = buildCashflowSeries([
      transaction({ amount: "-120", budget_category_id: "dining" }),
      transaction({ id: "refund", type: "transfer", amount: "120", budget_category_id: "dining" }),
      transaction({ id: "unassigned", amount: "-900" }),
    ], new Date(2026, 0, 1), new Date(2026, 1, 28), new Date(2026, 2, 1), "2024-03-14", new Set(["dining"]));
    expect(series[0].available).toBe(true);
    expect(series[0].partialHistory).toBe(false);
    expect(series[1].expenses).toBe(0);
  });
});
