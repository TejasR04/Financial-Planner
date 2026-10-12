import { expect, test } from "@playwright/test";

const apiBase = "http://127.0.0.1:8010/api/v1";

test("a signed-in user can create, use, and revoke a one-time Meridian agent token", async ({ page, request }) => {
  const email = `integrations-e2e-${Date.now()}@example.com`;
  const password = "correct-horse-battery-staple";

  const registered = await request.post(`${apiBase}/auth/register`, {
    data: { email, password, full_name: "Integrations E2E User" },
  });
  expect(registered.status()).toBe(201);

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/$/);

  await page.goto("/settings");
  await page.getByRole("button", { name: "Integrations" }).click();
  await expect(page.getByRole("heading", { name: "Agent access" })).toBeVisible();
  await expect(page.getByText("No agent tokens yet.")).toBeVisible();

  const listResponse = page.waitForResponse((response) =>
    response.request().method() === "GET" && response.url().endsWith("/api/v1/integrations/tokens"),
  );
  await page.getByRole("button", { name: "Create token" }).click();
  const createdToken = page.locator("code").filter({ hasText: /^mrd_/ });
  await expect(createdToken).toBeVisible();
  const secret = (await createdToken.innerText()).trim();
  expect(secret).toMatch(/^mrd_[A-Za-z0-9_-]+$/);
  const browserStorage = await page.evaluate(() => JSON.stringify({
    local: Object.keys(localStorage).map((key) => [key, localStorage.getItem(key)]),
    session: Object.keys(sessionStorage).map((key) => [key, sessionStorage.getItem(key)]),
  }));
  expect(browserStorage).not.toContain(secret);

  const listedResponse = await listResponse;
  expect(listedResponse.ok()).toBeTruthy();
  const listed = await listedResponse.json() as { data: Record<string, unknown>[] };
  expect(listed.data).toHaveLength(1);
  expect(listed.data[0]).toMatchObject({ name: "Hermes daily report", scope: "reports:read" });
  expect(listed.data[0]).not.toHaveProperty("token");
  expect(JSON.stringify(listed)).not.toContain(secret);

  const authorized = await request.get(`${apiBase}/reports/current`, {
    headers: { Authorization: `Bearer ${secret}` },
  });
  expect(authorized.status()).toBe(200);

  await page.reload();
  await page.getByRole("button", { name: "Integrations" }).click();
  await expect(page.getByText(secret, { exact: true })).toHaveCount(0);
  await expect(page.getByText(/mrd_[A-Za-z0-9_-]+••••••/)).toBeVisible();

  await page.getByRole("button", { name: "Revoke" }).click();
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText(/Revoked /)).toBeVisible();

  const rejected = await request.get(`${apiBase}/reports/current`, {
    headers: { Authorization: `Bearer ${secret}` },
  });
  expect(rejected.status()).toBe(401);
});
