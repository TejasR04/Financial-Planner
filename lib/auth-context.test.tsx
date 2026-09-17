import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./auth-context";
import { api, setDemoMode } from "./api-client";
import { AuthGuard } from "@/components/auth-guard";

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
function Controls() {
  const { status, isDemo, toggleDemo } = useAuth();
  return <><p>{status}</p><button onClick={toggleDemo}>{isDemo ? "Exit demo" : "Try demo"}</button><AuthGuard><p>Plan visible</p></AuthGuard></>;
}
afterEach(() => { cleanup(); sessionStorage.clear(); setDemoMode(false); vi.restoreAllMocks(); });
it.each([false, true])("allows demo access and returns to the original authentication state (signed in: %s)", async (signedIn) => {
  vi.spyOn(api.auth, "refresh").mockImplementation(() => signedIn ? Promise.resolve({ access_token: "test", token_type: "bearer" }) : Promise.reject(new Error("No session")));
  render(<AuthProvider><Controls /></AuthProvider>);
  await waitFor(() => expect(screen.getByText(signedIn ? "authenticated" : "unauthenticated")).toBeVisible());
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Try demo" }));
  expect(screen.getByText("Plan visible")).toBeVisible();
  expect(sessionStorage.getItem("meridian-demo")).toBe("true");
  await user.click(screen.getByRole("button", { name: "Exit demo" }));
  expect(router.push).toHaveBeenLastCalledWith(signedIn ? "/" : "/login");
  expect(screen.getByText(signedIn ? "authenticated" : "unauthenticated")).toBeVisible();
});
it("restores demo access after reload without a signed-in session", async () => {
  sessionStorage.setItem("meridian-demo", "true");
  vi.spyOn(api.auth, "refresh").mockRejectedValue(new Error("No session"));
  render(<AuthProvider><Controls /></AuthProvider>);
  await waitFor(() => expect(screen.getByRole("button", { name: "Exit demo" })).toBeVisible());
  expect(screen.getByText("Plan visible")).toBeVisible();
});
