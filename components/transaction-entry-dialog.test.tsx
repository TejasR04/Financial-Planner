import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { TransactionEntryDialog } from "./transaction-entry-dialog";
import { api } from "@/lib/api-client";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("keeps transaction classification separate from money direction", async () => {
  const create = vi.spyOn(api.transactions, "create").mockResolvedValue({} as never);
  const user = userEvent.setup();
  render(<TransactionEntryDialog
    open
    accounts={[{ id: "checking", name: "Checking", type: "Depository", mask: "1234", balance: 1000, status: "manual", updated: "Today" }]}
    onClose={vi.fn()}
    onSaved={vi.fn()}
  />);

  await user.type(screen.getByLabelText("Merchant or description"), "Card payment");
  await user.selectOptions(screen.getByLabelText("Type"), "credit_card_payment");
  await user.selectOptions(screen.getByLabelText("Direction"), "out");
  await user.type(screen.getByLabelText("Amount"), "500");
  await user.click(screen.getByRole("button", { name: "Add transaction" }));

  await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({
    type: "credit_card_payment",
    amount: "-500",
  })));
});
