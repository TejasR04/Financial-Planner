import { expect, test } from "@playwright/test";

test("an existing user can sign in, and invalid credentials remain actionable", async ({
  page,
  request,
}) => {
  const email = `e2e-${Date.now()}@example.com`;
  const password = "correct-horse-battery-staple";

  const seeded = await request.post("http://127.0.0.1:8010/api/v1/auth/register", {
    data: { email, password, full_name: "E2E Test User" },
  });
  expect(seeded.status()).toBe(201);

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Invalid email or password", { exact: true })).toBeVisible();

  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/$/);
});
