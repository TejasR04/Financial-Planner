import { describe, expect, it } from "vitest";

import { displayProjectionDollars } from "@/lib/projection-dollars";

describe("displayProjectionDollars", () => {
  it("preserves model output in today's dollars", () => {
    expect(displayProjectionDollars(100_000, 20, 0.03, "today")).toBe(100_000);
  });

  it("inflates future-dollar output and clamps negative horizons", () => {
    expect(displayProjectionDollars(100, 2, 0.1, "future")).toBeCloseTo(121);
    expect(displayProjectionDollars(100, -2, 0.1, "future")).toBe(100);
  });
});
