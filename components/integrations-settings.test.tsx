import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  isDemo: false,
  listTokens: vi.fn(),
  createToken: vi.fn(),
  revokeToken: vi.fn(),
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ isDemo: mocks.isDemo }) }));
vi.mock("@/lib/api-client", () => ({
  api: { integrations: {
    tokens: mocks.listTokens,
    createToken: mocks.createToken,
    revokeToken: mocks.revokeToken,
  } },
  ApiError: class ApiError extends Error {},
  getMcpEndpoint: () => "https://meridian.example/mcp",
}));

import { IntegrationsSettings } from "@/components/integrations-settings";

const token = {
  id: "token-1",
  name: "Hermes",
  prefix: "mer_123",
  created_at: "2026-10-11T12:00:00Z",
  expires_at: "2027-10-11T12:00:00Z",
  revoked_at: null,
  scope: "reports:read" as const,
};

afterEach(cleanup);

beforeEach(() => {
  mocks.isDemo = false;
  mocks.listTokens.mockReset().mockResolvedValue({ data: [token] });
  mocks.createToken.mockReset().mockResolvedValue({ ...token, token: "secret-shown-once" });
  mocks.revokeToken.mockReset().mockResolvedValue(undefined);
});

describe("IntegrationsSettings", () => {
  it("creates a named token and displays its secret once", async () => {
    const user = userEvent.setup();
    render(<IntegrationsSettings />);
    await screen.findByText("Hermes");
    const nameInput = screen.getByLabelText("Token name");
    await user.clear(nameInput);
    await user.type(nameInput, "Daily Hermes");
    await user.click(screen.getByRole("button", { name: "Create token" }));

    expect(mocks.createToken).toHaveBeenCalledWith("Daily Hermes");
    expect(await screen.findByText("secret-shown-once")).toBeInTheDocument();
    expect(screen.getByText(/will not show it again/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Hide token" }));
    expect(screen.queryByText("secret-shown-once")).not.toBeInTheDocument();
  });

  it("offers a config with the MCP URL and environment reference, and confirms token revocation", async () => {
    const user = userEvent.setup();
    render(<IntegrationsSettings />);

    expect(await screen.findByText("Hermes")).toBeInTheDocument();
    expect(screen.getByText("https://meridian.example/mcp")).toBeInTheDocument();
    expect(screen.getByText(/Bearer \$\{MERIDIAN_AGENT_TOKEN\}/)).toBeInTheDocument();
    expect(screen.getByText(/get_daily_report/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Revoke" }));
    expect(screen.getByText("Revoke this token?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(mocks.revokeToken).toHaveBeenCalledWith("token-1"));
  });

  it("does not request or create credentials in demo mode", async () => {
    mocks.isDemo = true;
    render(<IntegrationsSettings />);

    expect(screen.getByText(/unavailable in demo mode/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create token" })).toBeDisabled();
    expect(mocks.listTokens).not.toHaveBeenCalled();
    fireEvent.submit(screen.getByRole("button", { name: "Create token" }).closest("form")!);
    expect(mocks.createToken).not.toHaveBeenCalled();
  });
});
