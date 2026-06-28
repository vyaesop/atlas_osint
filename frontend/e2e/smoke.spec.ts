import { test, expect } from "@playwright/test";

/**
 * Critical-path smoke test (Task 2): login → explore → graph renders.
 *
 * This is the one journey that, if broken, means the app is down for everyone.
 * It runs against a freshly seeded admin (see playwright.config.ts webServer).
 */

const ADMIN_EMAIL = "admin@atlas.example.com";
const ADMIN_PASSWORD = "ChangeMe123!"; // FIRST_ADMIN_PASSWORD default

test("login takes the analyst to the graph explorer", async ({ page }) => {
  await page.goto("/login");

  // Email is pre-filled with the admin address; set it explicitly to be safe.
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();

  // Successful auth redirects to the explorer.
  await page.waitForURL("**/explore");

  // The search bar is the always-present chrome of the explorer.
  await expect(
    page.getByPlaceholder(/search people, orgs, companies/i),
  ).toBeVisible();

  // The React Flow canvas (the graph itself) mounts client-side.
  await expect(page.locator(".react-flow")).toBeVisible({ timeout: 15_000 });
});

test("bad credentials are rejected", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: /sign in/i }).click();

  await expect(page.getByText(/invalid email or password/i)).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});
