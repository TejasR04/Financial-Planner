import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("forwards native behavior and applies variants", async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();

    render(
      <Button variant="outline" size="sm" onClick={onClick}>
        Save changes
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Save changes" });
    expect(button).toHaveClass("border-border", "h-7");
    await user.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("preserves disabled button semantics", () => {
    render(<Button disabled>Unavailable</Button>);
    expect(screen.getByRole("button", { name: "Unavailable" })).toBeDisabled();
  });
});
