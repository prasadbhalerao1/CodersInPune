import { expect, test } from "@playwright/test";

// CI-safe: no account needed. Protected pages must never render without a session.

for (const path of ["/workspaces", "/w/00000000-0000-7000-8000-000000000000", "/invitations"]) {
  test(`${path} requires sign-in`, async ({ page }) => {
    const response = await page.goto(path, { waitUntil: "commit" });
    await page.waitForURL((url) => !url.pathname.startsWith(path), { timeout: 15_000 });
    expect(page.url()).toMatch(/authkit|workos|sign-in/);
    expect(response?.status() ?? 0).toBeLessThan(500);
  });
}

test("the GitHub callback rejects requests without a session", async ({ page }) => {
  await page.goto("/integrations/github/callback?code=x&installation_id=1&state=forged");
  await page.waitForURL((url) => !url.pathname.startsWith("/integrations/github/callback"));
  expect(page.url()).not.toContain("connected=1");
});
