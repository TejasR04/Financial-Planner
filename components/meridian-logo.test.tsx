import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MeridianLogo, MeridianMark } from "@/components/meridian-logo";

describe("Meridian branding", () => {
  it("renders an accessible vector mark", () => {
    render(<MeridianMark />);
    expect(screen.getByRole("img", { name: "Meridian" })).toBeInTheDocument();
  });

  it("supports both lockup and mark-only variants", () => {
    const { rerender } = render(<MeridianLogo />);
    expect(screen.getByText("Meridian")).toBeInTheDocument();
    rerender(<MeridianLogo variant="mark" />);
    expect(screen.queryByText("Meridian")).not.toBeInTheDocument();
  });
});
