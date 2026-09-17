import { describe, expect, it } from "vitest";

import { escapeCsvCell } from "@/lib/transaction-export";

describe("escapeCsvCell", () => {
  it.each(["=1+1", "+SUM(A1:A2)", "-2+3", "@cmd", "  =HYPERLINK(\"x\")", "\t+cmd", "\r@cmd"])(
    "neutralizes spreadsheet formula input %j",
    (value) => {
      expect(escapeCsvCell(value)).toBe(`"'${value.replaceAll('"', '""')}"`);
    },
  );

  it("still applies standard CSV quote escaping", () => {
    expect(escapeCsvCell('Coffee "shop"')).toBe('"Coffee ""shop"""');
  });

  it("allows numeric fields to retain a negative sign when explicitly requested", () => {
    expect(escapeCsvCell("-12.50", false)).toBe('"-12.50"');
  });
});
