import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RecommendationCard } from "@/components/recommendation-card";

const { update, refresh } = vi.hoisted(() => ({
  update: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
  api: { recommendations: { update } },
}));
vi.mock("@/lib/data-provider", () => ({ useDataRefresh: () => refresh }));

const recommendation = {
  id: "recommendation-1",
  title: "Move excess cash",
  body: "Earn more interest on cash above your reserve.",
  impact: "$120/yr",
  impactValue: 120,
  effort: "Low" as const,
  category: "Cash Management",
  confidence: 0.9,
};

describe("RecommendationCard", () => {
  beforeEach(() => {
    update.mockReset();
    refresh.mockReset();
  });

  afterEach(cleanup);

  it("describes the status-only action truthfully", () => {
    render(<RecommendationCard rec={recommendation} />);
    expect(screen.getByRole("button", { name: "Mark as done" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();
  });

  it("shows an actionable error when a status update fails", async () => {
    update.mockRejectedValueOnce(new Error("offline"));
    render(<RecommendationCard rec={recommendation} />);

    await userEvent.click(screen.getByRole("button", { name: "Mark as done" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not mark this recommendation as done. Please try again.",
    );
    expect(refresh).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Mark as done" })).toBeEnabled();
  });
});
