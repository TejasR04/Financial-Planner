import { expect, it } from "vitest";
import { applyToTransactions } from "./bulk-transactions";

it("reports failed rows without losing successful updates", async () => {
  const result = await applyToTransactions(["one", "two", "three"], async (id) => {
    if (id === "two") throw new Error("Category not allowed");
  });
  expect(result.succeeded).toEqual(["one", "three"]);
  expect(result.failed).toEqual(["two"]);
  expect(result.errors).toEqual(["Category not allowed"]);
});
