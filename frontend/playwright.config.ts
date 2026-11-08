import { defineConfig, devices } from "@playwright/test";

/**
 * Two suites:
 * - `public`: CI-safe. No credentials; checks that protected routes require sign-in.
 * - `smoke`: local, real WorkOS account. `pnpm e2e:login` opens ordinary Chrome once so a
 *   person can sign in (e2e/login-chrome.mjs); the session is saved to e2e/.auth/ (git-ignored) and reused.
 * Both run against a running stack (`pnpm dev` + relay-api + relay-worker).
 */
const baseURL = process.env.RELAY_E2E_BASE_URL ?? "http://localhost:3000";
// Real-account runs use the installed Google Chrome (a clean, separate profile).
const chrome = { ...devices["Desktop Chrome"], channel: process.env.RELAY_E2E_CHANNEL ?? "chrome" };

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [["list"]],
  use: { baseURL, trace: "retain-on-failure" },
  projects: [
    { name: "public", testMatch: /public\.spec\.ts/, use: { ...devices["Desktop Chrome"] } },
    {
      name: "smoke",
      testMatch: /smoke\.spec\.ts/,
      use: { ...chrome, storageState: "e2e/.auth/user.json" },
    },
  ],
});
