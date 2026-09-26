import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ProjectionAssumptions } from "@/components/projection-assumptions";

const mocks = vi.hoisted(() => ({
  profile: null as null | Record<string, unknown>,
  retirement: vi.fn(),
  createScenario: vi.fn(),
}));

vi.mock("@/lib/data-provider", () => ({
  useProfileSummary: () => mocks.profile,
  useCurrentRetirementBalance: () => 100000,
  useDataRefresh: () => vi.fn(),
}));
vi.mock("@/lib/api-client", () => ({
  ApiError: class extends Error {},
  api: {
    simulations: { retirement: mocks.retirement },
    scenarios: { create: mocks.createScenario },
  },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function profile(currentAge: number) {
  mocks.profile = {
    currentAge,
    currentRetirementBalance: 100000,
    netWorthToday: 100000,
    targetRetirementAge: 65,
    expectedReturn: "0.065",
    inflationRate: "0.028",
    defaultWithdrawalRate: 0.04,
    monthlySurplusEstimate: 500,
  };
}

it("keeps the retirement age slider valid for users age 80 to 93", async () => {
  profile(80);
  render(<ProjectionAssumptions dollarDisplay="today" />);

  const slider = screen.getByLabelText("Target retirement age") as HTMLInputElement;
  await screen.findByText("Retirement balance at age 81");

  expect(slider.min).toBe("81");
  expect(slider.max).toBe("94");
  expect(slider.value).toBe("81");
  expect(slider.disabled).toBe(false);
});

it("explains and disables quick projections when no retirement year remains before age 95", () => {
  profile(94);
  render(<ProjectionAssumptions dollarDisplay="today" />);

  expect(screen.getByText(/use age 95 as the life expectancy/)).toBeInTheDocument();
  expect(screen.getByLabelText("Target retirement age")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Save as scenario" })).toBeDisabled();
  expect(mocks.retirement).not.toHaveBeenCalled();
});
