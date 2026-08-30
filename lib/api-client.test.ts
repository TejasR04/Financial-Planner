import { afterEach, describe, expect, it, vi } from "vitest";
import { api, formatApiErrorDetail } from "@/lib/api-client";

describe("formatApiErrorDetail", () => {
  it("turns structured validation details into readable field messages", () => {
    expect(formatApiErrorDetail([
      { loc: ["body", "term_months"], msg: "Field required" },
      { loc: ["body", "origination_date"], msg: "Field required" },
    ], "Request failed")).toBe("term months: Field required; origination date: Field required");
  });
});

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

describe("transactions.list", () => {
  afterEach(() => vi.restoreAllMocks());

  it("sends transaction search and user budget category filters separately", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      data: [], total: 0, limit: 50, offset: 0,
    }), { status: 200, headers: { "Content-Type": "application/json" } }));

    await api.transactions.list({ search: "12.50", budgetCategoryId: "category-id", cashFlowOnly: true });

    const url = new URL(String(fetchMock.mock.calls[0]?.[0]));
    expect(url.searchParams.get("search")).toBe("12.50");
    expect(url.searchParams.get("budget_category_id")).toBe("category-id");
    expect(url.searchParams.get("cash_flow_only")).toBe("true");
    expect(url.searchParams.has("category")).toBe(false);
  });
});

describe("accounts archive recovery", () => {
  afterEach(() => vi.restoreAllMocks());

  it("uses explicit archive, archived-list, and restore endpoints", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = new URL(String(input));
      if (url.pathname.endsWith("/archived")) {
        return new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (init?.method === "POST") {
        return new Response(null, { status: 204 });
      }
      return new Response(null, { status: 204 });
    });

    await api.accounts.archived();
    await api.accounts.restore("account-id");
    await api.accounts.archive("account-id");

    expect(new URL(String(fetchMock.mock.calls[0]?.[0])).pathname).toBe("/api/v1/accounts/archived");
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: "POST" });
    expect(new URL(String(fetchMock.mock.calls[1]?.[0])).pathname).toBe("/api/v1/accounts/account-id/restore");
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({ method: "DELETE" });
    expect(new URL(String(fetchMock.mock.calls[2]?.[0])).pathname).toBe("/api/v1/accounts/account-id");
  });

  it("supports the disconnected imported data summary and purge", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      const body = init?.method === "DELETE"
        ? { account_count: 2, transaction_count: 12, deleted: true }
        : { account_count: 2, transaction_count: 12 };
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    await expect(api.accounts.disconnectedImportedDataSummary()).resolves.toMatchObject({ account_count: 2 });
    await expect(api.accounts.permanentlyDeleteDisconnectedImportedData()).resolves.toMatchObject({ deleted: true });
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBeUndefined();
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: "DELETE" });
  });
});
