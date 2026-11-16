import { test as setup } from "@playwright/test";

// Signs in through the one-click sample Owner account (`/sign-in?as=owner`), the same route
// judges use, and saves the session for the signed-in suites. No password is typed here: the
// app signs the sample account in server-side. A personal session from `pnpm e2e:login` can
// still be used instead by skipping this project.
setup("sign in as the sample Owner", async ({ page }) => {
  await page.goto("/sign-in?as=owner");
  await page.waitForURL(/\/workspaces/, { timeout: 60_000 });
  await page.context().storageState({ path: "e2e/.auth/user.json" });
});
