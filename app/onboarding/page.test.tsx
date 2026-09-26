import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import OnboardingPage from "./page";
import { api } from "@/lib/api-client";

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ status: "authenticated" }) }));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  router.push.mockReset();
  router.replace.mockReset();
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => { resolve = res; });
  return { promise, resolve };
}

it("waits for both saves, reports the partial result, and allows a safe retry", async () => {
  vi.spyOn(api.users, "me").mockResolvedValue({
    id: "user-1", email: "user@example.com", full_name: "User", base_currency: "USD", date_of_birth: "1990-01-01",
  });
  vi.spyOn(api.users, "planningProfile").mockResolvedValue({
    target_retirement_age: 65,
    target_equity_allocation: "0.60",
    default_withdrawal_rate: "0.04",
    include_social_security: true,
    expected_return: "0.065",
    inflation_rate: "0.028",
    target_savings_rate: null,
    cash_reserve_target: null,
  });
  const profileSave = deferred<Awaited<ReturnType<typeof api.users.updateMe>>>();
  const updateMe = vi.spyOn(api.users, "updateMe").mockReturnValueOnce(profileSave.promise).mockResolvedValue({
    id: "user-1", email: "user@example.com", full_name: "User", base_currency: "USD", date_of_birth: "1990-01-01",
  });
  const updatePlanning = vi.spyOn(api.users, "updatePlanningProfile")
    .mockRejectedValueOnce(new Error("temporary planning failure"))
    .mockResolvedValue({
      target_retirement_age: 65,
      target_equity_allocation: "0.60",
      default_withdrawal_rate: "0.04",
      include_social_security: true,
      expected_return: "0.065",
      inflation_rate: "0.028",
      target_savings_rate: null,
      cash_reserve_target: null,
    });

  render(<OnboardingPage />);
  await screen.findByRole("button", { name: "Save and continue" });
  fireEvent.click(screen.getByRole("button", { name: "Save and continue" }));

  await waitFor(() => {
    expect(updateMe).toHaveBeenCalledTimes(1);
    expect(updatePlanning).toHaveBeenCalledTimes(1);
  });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(router.push).not.toHaveBeenCalled();

  profileSave.resolve({
    id: "user-1", email: "user@example.com", full_name: "User", base_currency: "USD", date_of_birth: "1990-01-01",
  });
  expect(await screen.findByRole("alert")).toHaveTextContent("About you saved; retirement plan couldn't be saved");
  expect(router.push).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("button", { name: "Save and continue" }));
  await waitFor(() => expect(router.push).toHaveBeenCalledWith("/"));
  expect(updateMe).toHaveBeenCalledTimes(2);
  expect(updatePlanning).toHaveBeenCalledTimes(2);
});
