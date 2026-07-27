import { expect, test } from "@playwright/test";

test("Insights separates Gemini from rule-based analysis and renders tool use", async ({
  page,
}) => {
  const email = `assistant-e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("Full name").fill("Assistant E2E User");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
  await page.getByRole("button", { name: "Skip for now" }).click();

  await page.route("**/api/v1/agent/history", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }
    await route.fulfill({ status: 204 });
  });
  await page.route("**/api/v1/agent/chat", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        reply: "Your projection was calculated with Meridian's retirement model.",
        tool_calls: [{ tool: "forecast_retirement", arguments: {} }],
        structured_results: [{ tool: "forecast_retirement", result: {} }],
      }),
    });
  });

  await page.goto("/insights");
  await expect(
    page.getByRole("heading", { name: "Gemini financial assistant" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Rule-based insights" })).toBeVisible();
  await expect(
    page.getByText("These results do not use Gemini.", { exact: false }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Analyze my plan" }).click();
  await expect(
    page.getByText("Your projection was calculated with Meridian's retirement model."),
  ).toBeVisible();
  await expect(page.getByText("forecast_retirement", { exact: true })).toBeVisible();
});
