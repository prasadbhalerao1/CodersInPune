import { expect, test } from "@playwright/test";

// Run with `pnpm e2e:login`: a browser opens on the WorkOS sign-in page. Sign in yourself
// (any method); the test only waits for Relay to load, then saves the session cookie.
// Credentials are never typed or stored by the test.
test("sign in once and save the session", async ({ page }) => {
  await page.goto("/sign-in");
  await page.waitForURL(/localhost:3000\/(workspaces|w\/)/, { timeout: 290_000 });
  await expect(page.getByText("Relay").first()).toBeVisible();
  await page.context().storageState({ path: "e2e/.auth/user.json" });
});
