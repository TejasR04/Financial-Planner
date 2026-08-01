import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DialogShell } from "@/components/ui/dialog-shell";

describe("DialogShell", () => {
  it("moves focus inside, traps tab navigation, closes on Escape, and restores focus", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    const trigger = document.createElement("button");
    trigger.textContent = "Open dialog";
    document.body.append(trigger);
    trigger.focus();

    const { unmount } = render(
      <DialogShell onClose={onClose} ariaLabel="Test dialog">
        <button>First action</button>
        <button>Last action</button>
      </DialogShell>,
    );

    const first = screen.getByRole("button", { name: "First action" });
    const last = screen.getByRole("button", { name: "Last action" });
    await waitFor(() => expect(first).toHaveFocus());

    last.focus();
    await user.tab();
    expect(first).toHaveFocus();

    await user.tab({ shift: true });
    expect(last).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();

    unmount();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("keeps a busy dialog open", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <DialogShell onClose={onClose} closeDisabled ariaLabel="Busy dialog">
        <button>Continue</button>
      </DialogShell>,
    );

    await user.keyboard("{Escape}");
    expect(onClose).not.toHaveBeenCalled();
  });
});
