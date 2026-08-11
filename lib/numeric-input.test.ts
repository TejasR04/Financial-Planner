import { describe, expect, it } from "vitest";

import { sanitizeUnsignedNumberInput } from "./numeric-input";

describe("sanitizeUnsignedNumberInput", () => {
  it("removes letters and exponent notation", () => {
    expect(sanitizeUnsignedNumberInput("4e2abc")).toBe("42");
  });

  it("preserves one decimal point", () => {
    expect(sanitizeUnsignedNumberInput("6.5.2")).toBe("6.52");
    expect(sanitizeUnsignedNumberInput("12.")).toBe("12.");
  });

  it("removes signs from unsigned values", () => {
    expect(sanitizeUnsignedNumberInput("-$+500.25")).toBe("500.25");
  });

  it("supports integer-only inputs", () => {
    expect(sanitizeUnsignedNumberInput("65 years", false)).toBe("65");
  });
});
