import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { FinancialDetailsDialog } from "./financial-details-dialog";
import { api } from "@/lib/api-client";

afterEach(() => vi.restoreAllMocks());

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
