import { describe, expect, it } from "vitest";
import { retirementPortfolioBalance } from "@/lib/retirement-portfolio";

describe("retirement portfolio balance", () => {
  it("includes brokerage and retirement accounts once, excluding cash accounts and liabilities", () => {
    expect(retirementPortfolioBalance([
      { type: "investment", balance: "300000" },
      { type: "retirement", balance: "100000" },
      { type: "depository", balance: "20000" },
      { type: "loan", balance: "-50000" },
    ])).toBe(400000);
  });
});
