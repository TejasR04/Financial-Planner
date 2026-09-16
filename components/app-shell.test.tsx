import { render, screen, within, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { AppShell } from "@/components/app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));
vi.mock("@/lib/data-provider", () => ({ useDataError: () => null, useUserAccount: () => null }));
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ logout: vi.fn() }) }));
vi.mock("@/components/theme-provider", () => ({ ThemeProvider: ({ children }: { children: React.ReactNode }) => children }));
vi.mock("@/components/command-palette", () => ({ CommandPalette: () => null }));
vi.mock("@/components/topbar", () => ({ Topbar: ({ onOpenNavigation }: { onOpenNavigation: () => void }) => <button onClick={onOpenNavigation}>Open navigation</button> }));

afterEach(() => vi.unstubAllGlobals());

it("opens navigation, traps focus, and closes on Escape, outside click, or navigation", async () => {
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  const user = userEvent.setup();
  render(<AppShell><p>Page content</p></AppShell>);
  const trigger = screen.getByRole("button", { name: "Open navigation" });
  await user.click(trigger);
  const dialog = screen.getByRole("dialog", { name: "Navigation" });
  const close = within(dialog).getByRole("button", { name: "Close navigation" });
  await waitFor(() => expect(close).toHaveFocus());
  await user.tab({ shift: true });
  expect(within(dialog).getByRole("button", { name: "Sign out" })).toHaveFocus();
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
  await user.click(trigger);
  fireEvent.mouseDown(screen.getByRole("dialog").parentElement!);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await user.click(trigger);
  await user.click(within(screen.getByRole("dialog")).getByRole("link", { name: "Overview" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
