import { afterEach, describe, expect, it, vi } from "vitest";
import { ResponseCache, RESPONSE_CACHE_TTL_MS } from "@/lib/response-cache";

afterEach(() => vi.useRealTimers());

describe("temporary financial response cache", () => {
  it("caches by exact query, clones values, and expires", async () => {
    vi.useFakeTimers();
    const cache = new ResponseCache();
    const loader = vi.fn(async () => ({ amount: 10 }));
    (await cache.load("month=09", loader)).amount = 99;
    expect(await cache.load("month=09", loader)).toEqual({ amount: 10 });
    expect(loader).toHaveBeenCalledTimes(1);
    await cache.load("month=08", loader);
    vi.advanceTimersByTime(RESPONSE_CACHE_TTL_MS);
    await cache.load("month=09", loader);
    expect(loader).toHaveBeenCalledTimes(3);
  });

  it("does not let an old request repopulate an invalidated cache", async () => {
    const cache = new ResponseCache();
    let resolve!: (value: number) => void;
    const pending = cache.load("accounts", () => new Promise<number>((done) => { resolve = done; }));
    cache.clear();
    resolve(1);
    await pending;
    expect(await cache.load("accounts", async () => 2)).toBe(2);
  });

  it("does not cache failures or aborted requests", async () => {
    const cache = new ResponseCache();
    await expect(cache.load("budget", async () => { throw new Error("offline"); })).rejects.toThrow("offline");
    const controller = new AbortController();
    await expect(cache.load("budget", async () => { controller.abort(); return 1; }, controller.signal)).rejects.toMatchObject({ name: "AbortError" });
    expect(await cache.load("budget", async () => 2)).toBe(2);
  });
});
