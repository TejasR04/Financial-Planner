import { describe, expect, it } from "vitest";

import { formatCurrency, formatPercent } from "@/lib/data";

describe("display formatting", () => {
  it("formats currency signs, rounding, and compact units", () => {
    expect(formatCurrency(1234.56)).toBe("$1,235");
    expect(formatCurrency(-42, { sign: true })).toBe("-$42");
    expect(formatCurrency(42, { sign: true })).toBe("+$42");
    expect(formatCurrency(1_500, { compact: true })).toBe("$1.5K");
    expect(formatCurrency(2_000_000, { compact: true })).toBe("$2.0M");
    expect(formatCurrency(3_000_000_000, { compact: true })).toBe("$3.0B");
  });

  it("formats percentages with configurable precision and sign", () => {
    expect(formatPercent(4.125)).toBe("4.1%");
    expect(formatPercent(4.125, { sign: true, digits: 2 })).toBe("+4.13%");
    expect(formatPercent(-2, { sign: true, digits: 0 })).toBe("-2%");
  });
});
