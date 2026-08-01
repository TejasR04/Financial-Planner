import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api-client";

describe("transactions.listAll", () => {
  afterEach(() => vi.restoreAllMocks());

  it("paginates within the backend's 200-row limit", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = new URL(String(input));
      const offset = Number(url.searchParams.get("offset") ?? 0);
      const count = offset === 0 ? 200 : 50;
      return new Response(JSON.stringify({
        data: Array.from({ length: count }, (_, index) => ({ id: `${offset + index}` })),
        total: 250,
        limit: 200,
        offset,
      }), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    const rows = await api.transactions.listAll({ since: "2025-09-01" });

    expect(rows).toHaveLength(250);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    for (const [input] of fetchMock.mock.calls) {
      expect(new URL(String(input)).searchParams.get("limit")).toBe("200");
    }
  });

  it("forwards cancellation to every page request", async () => {
    const controller = new AbortController();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new DOMException("Aborted", "AbortError"),
    );
    controller.abort();

    await expect(api.transactions.listAll({}, controller.signal)).rejects.toMatchObject({
      name: "AbortError",
    });
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ signal: controller.signal });
  });
});
