import type { ApiTransaction } from "@/lib/api-client";
import { budgetCashFlowAmounts } from "@/lib/budget-cash-flow";
import type { CashflowPoint } from "@/lib/data";

/** Date and cash-flow transformations used while mapping dashboard API data. */
export function ageFromBirthDate(dob: string | null, today = new Date()): number | null {
  if (!dob) return null;
  const [birthYear, birthMonth, birthDay] = dob.slice(0, 10).split("-").map(Number);
  if (!birthYear || !birthMonth || !birthDay) return null;
  let age = today.getFullYear() - birthYear;
  const hadBirthday =
    today.getMonth() + 1 > birthMonth
    || (today.getMonth() + 1 === birthMonth && today.getDate() >= birthDay);
  if (!hadBirthday) age -= 1;
  return age;
}

export function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  const timestamp = new Date(iso);
  if (Number.isNaN(timestamp.getTime())) return "—";
  return timestamp.toLocaleString("en-US", {
    timeZone: "America/New_York",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export function formatShortDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export function monthKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

export function twelveMonthWindow(today = new Date()) {
  const start = new Date(today.getFullYear(), today.getMonth() - 11, 1);
  const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
  return {
    start,
    startDate: `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, "0")}-01`,
    end,
  };
}

export function buildCashflowSeries(
  transactions: ApiTransaction[],
  start: Date,
  end: Date,
  today = new Date(),
  historyStart?: string | null,
  activeCategoryIds?: ReadonlySet<string>,
): CashflowPoint[] {
  const firstDate = historyStart ?? transactions.reduce(
    (first, transaction) => transaction.posted_at < first ? transaction.posted_at : first,
    "9999-12-31",
  );
  const currentMonth = monthKey(today);
  const buckets = new Map<string, { income: number; expenses: number }>();
  const cursor = new Date(start.getFullYear(), start.getMonth(), 1);
  while (cursor <= end) {
    buckets.set(monthKey(cursor), { income: 0, expenses: 0 });
    cursor.setMonth(cursor.getMonth() + 1);
  }

  for (const transaction of transactions) {
    const posted = new Date(`${transaction.posted_at}T00:00:00`);
    const bucket = buckets.get(monthKey(posted));
    if (!bucket) continue;
    const amounts = budgetCashFlowAmounts(transaction, activeCategoryIds);
    bucket.income += amounts.income;
    bucket.expenses += amounts.expenses;
  }

  return Array.from(buckets.entries()).map(([key, value]) => {
    const [year, month] = key.split("-");
    return {
      month: new Date(Number(year), Number(month) - 1, 1).toLocaleDateString("en-US", { month: "short" }),
      monthKey: key,
      available: key >= firstDate.slice(0, 7),
      incomplete: key === currentMonth,
      partialHistory: key === firstDate.slice(0, 7) && firstDate.slice(8, 10) !== "01",
      income: value.income,
      expenses: value.expenses,
    };
  });
}
