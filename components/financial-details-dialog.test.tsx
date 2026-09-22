import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { FinancialDetailsDialog } from "./financial-details-dialog";
import { api } from "@/lib/api-client";

vi.mock("@/lib/data-provider", () => ({ useDataRefresh: () => vi.fn() }));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("selects a merchant from transaction history before saving a future payment rule", async () => {
  vi.spyOn(api.accounts, "liability").mockResolvedValue(null);
  vi.spyOn(api.accounts, "balanceRules").mockResolvedValue([]);
  const search = vi.spyOn(api.transactions, "merchants").mockResolvedValue(["Acme Auto Loan"]);
  const save = vi.spyOn(api.accounts, "createBalanceRule").mockResolvedValue({
    id: "rule", account_id: "loan", mode: "merchant", merchant_pattern: "acme auto loan",
    amount: null, frequency: null, next_run_date: null, active: true, created_at: "2026-09-15",
  });
  const user = userEvent.setup();
  render(<FinancialDetailsDialog account={{ id: "loan", name: "Auto loan", type: "Loan", mask: "", balance: -500, status: "manual", updated: "Today" }} onClose={vi.fn()} />);
  await user.selectOptions(screen.getAllByRole("combobox")[0], "merchant");
  const add = screen.getByRole("button", { name: "Add automatic payment" });
  expect(add).toBeDisabled();
  await user.type(screen.getByRole("textbox", { name: "Search payment merchants" }), "Acme");
  await waitFor(() => expect(search).toHaveBeenCalledWith("Acme", expect.any(AbortSignal)));
  await user.click(await screen.findByRole("button", { name: "Acme Auto Loan" }));
  expect(add).toBeEnabled();
  await user.click(add);
  await waitFor(() => expect(save).toHaveBeenCalledWith("loan", { mode: "merchant", merchant_pattern: "Acme Auto Loan" }));
  expect(await screen.findByText(/Merchant matches/)).toBeInTheDocument();
});

it("does not let a late debt response populate a different account", async () => {
  let resolveFirst!: (value: Awaited<ReturnType<typeof api.accounts.liability>>) => void;
  vi.spyOn(api.accounts, "liability").mockImplementation((id) => id === "first"
    ? new Promise((resolve) => { resolveFirst = resolve; })
    : Promise.resolve(null));
  vi.spyOn(api.accounts, "balanceRules").mockResolvedValue([]);
  const first = { id: "first", name: "First loan", type: "Loan" as const, mask: "", balance: -1000, status: "manual" as const, updated: "Today" };
  const second = { ...first, id: "second", name: "Second loan" };
  const view = render(<FinancialDetailsDialog account={first} onClose={vi.fn()} />);

  view.rerender(<FinancialDetailsDialog account={second} onClose={vi.fn()} />);
  await waitFor(() => expect(screen.getByRole("button", { name: "Save" })).toBeEnabled());
  resolveFirst({ id: "details", account_id: "first", principal: "1000", interest_rate: "0.05", term_months: 12, minimum_payment: "100", origination_date: null });

  await waitFor(() => expect(screen.getByPlaceholderText("Original principal (optional)")).toHaveValue(null));
  expect(screen.getByText(/Second loan/)).toBeVisible();
});

it("adds a monthly contribution rule to a manual retirement account", async () => {
  vi.spyOn(api.accounts, "holdings").mockResolvedValue([]);
  vi.spyOn(api.accounts, "contributionRules").mockResolvedValue([]);
  const save = vi.spyOn(api.accounts, "createContributionRule").mockResolvedValue({
    id: "contribution-rule",
    account_id: "retirement",
    amount: "250",
    day_of_month: 30,
    next_run_date: "2026-09-30",
    active: true,
    created_at: "2026-09-22T00:00:00Z",
  });
  const user = userEvent.setup();
  render(<FinancialDetailsDialog account={{ id: "retirement", name: "401(k)", type: "Retirement", mask: "", balance: 1000, status: "manual", updated: "Today" }} onClose={vi.fn()} />);

  await user.type(await screen.findByRole("spinbutton", { name: "Contribution amount" }), "250");
  await user.selectOptions(screen.getByRole("combobox", { name: "Contribution day" }), "30");
  await user.click(screen.getByRole("button", { name: "Add recurring contribution" }));

  await waitFor(() => expect(save).toHaveBeenCalledWith("retirement", { amount: "250", day_of_month: 30 }));
  expect(await screen.findByText(/\$250\.00 on the 30th/)).toBeInTheDocument();
});
