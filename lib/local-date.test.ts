import { describe, expect, it } from "vitest";
import { localDateKey, localMonthKey } from "@/lib/local-date";

describe("local date keys", () => {
  it("formats local calendar fields without converting through UTC", () => {
    const localDate = new Date(2026, 0, 2, 23, 59, 59);

    expect(localDateKey(localDate)).toBe("2026-01-02");
    expect(localMonthKey(localDate)).toBe("2026-01");
  });

  it("pads single-digit months and days", () => {
    expect(localDateKey(new Date(2026, 8, 7))).toBe("2026-09-07");
  });
});
