import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { NotificationsSettings } from "@/components/notifications-settings";

afterEach(cleanup);

describe("NotificationsSettings", () => {
  it("keeps every unavailable notification control disabled and clearly labeled", () => {
    render(<NotificationsSettings />);

    expect(screen.getByText("Notification delivery is coming soon")).toBeInTheDocument();
    const switches = screen.getAllByRole("switch");
    expect(switches).toHaveLength(5);
    for (const control of switches) {
      expect(control).toBeDisabled();
      expect(control).toHaveAttribute("aria-checked", "false");
    }
    expect(screen.getAllByText(/Coming soon$/)).toHaveLength(5);
  });
});
