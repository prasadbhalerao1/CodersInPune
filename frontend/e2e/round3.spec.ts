import { expect, type Page, test } from "@playwright/test";

// The judge journey through the three Round 3 features, on a fresh sample workspace.
// Starts at the landing page and only clicks what a person can see (no deep links).
// Local only: needs the saved real-account session (see playwright.config.ts).

test.describe.configure({ mode: "serial" });

let overview = "";

async function settle(page: Page) {
  await page.waitForLoadState("networkidle"); // a click before hydration is lost
}

async function sidebar(page: Page, label: string) {
  await page
    .getByRole("navigation", { name: "Workspace" })
    .getByRole("link", { name: label })
    .click();
  await settle(page);
}

test("from the landing page into a fresh sample workspace", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/");
  await page.getByRole("link", { name: "Go to your workspaces →" }).first().click();
  await page.waitForURL(/\/workspaces$/);
  await settle(page);
  await page.getByRole("button", { name: "Create sample workspace" }).click();
  // Samples are limited to a few per person per day; after that, open an existing one.
  const limited = page.getByRole("alert").filter({ hasText: /several sample workspaces/ });
  await Promise.race([
    page.waitForURL(/\/w\/[0-9a-f-]{36}$/, { timeout: 90_000 }).catch(() => undefined),
    limited.waitFor({ timeout: 90_000 }).catch(() => undefined),
  ]);
  const reused = await limited.isVisible();
  if (reused) {
    // Same-named workspaces are listed oldest first: the last is the newest sample.
    await page
      .getByRole("link", { name: /Northwind Labs \(demo\)/ })
      .last()
      .click();
    await page.waitForURL(/\/w\/[0-9a-f-]{36}$/);
  }
  await settle(page);
  overview = new URL(page.url()).pathname;
  // A fresh sample has an approved handover addressed to you (a reused one may be done).
  if (!reused) await expect(page.getByText("A handover is waiting for you")).toBeVisible();
  await expect(page.getByLabel("Continuity health")).toBeVisible();
});

test("memory replay: filter, play, inspect, explain and ask", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto(overview);
  await sidebar(page, "Responsibilities");
  await page.getByRole("link", { name: "Production deployments", exact: true }).first().click();
  await settle(page);
  await page.getByRole("link", { name: "Memory replay" }).click();
  await page.waitForURL(/\/timeline$/);
  await settle(page);

  const filters = page.getByRole("group", { name: "Filter by category" });
  await filters.getByRole("button", { name: /Incident/ }).click();
  const events = page.getByRole("region", { name: "Events" });
  await expect(events.getByText("Checkout outage after payments-api release")).toBeVisible();
  await expect(events.getByText("Add canary stage to the payments-api pipeline")).toHaveCount(0);
  await filters.getByRole("button", { name: /^All/ }).click();

  await page.getByRole("button", { name: "Replay history" }).click();
  await page.waitForTimeout(2_000);
  await page.getByRole("button", { name: "Pause" }).click();

  await page.getByRole("button", { name: "Inspect" }).first().click();
  const inspector = page.getByRole("region", { name: "Event details" });
  await expect(inspector.getByText("Fact")).toBeVisible();

  // With AI configured this writes a cited reading; without, it says why. Either is honest.
  // A stored reading opens straight away (with Regenerate); otherwise ask for one.
  const explain = page.getByRole("button", { name: "Explain this history" });
  if (await explain.isVisible()) await explain.click();
  await expect(
    page.getByText(/Inferred ·|AI is not configured|switched off|could not answer/).first(),
  ).toBeVisible({ timeout: 90_000 });

  await page.getByLabel("Your question").fill("Why does every payments-api deploy need a canary?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(
    page.getByText(/From the history|Search results, not an answer|Not in the history/).first(),
  ).toBeVisible({ timeout: 90_000 });
});

test("what if: Arjun away for two weeks, compare cover, nothing changes", async ({ page }) => {
  await page.goto(overview);
  await sidebar(page, "People & Teams");
  await page
    .getByRole("link", { name: "Arjun Rao", exact: true })
    .filter({ visible: true })
    .first()
    .click();
  await settle(page);
  await page.getByRole("link", { name: "What if Arjun is unavailable?" }).click();
  await settle(page);
  await page.getByLabel("is unavailable for").selectOption({ label: "2 weeks" });
  await page.getByRole("button", { name: "Run simulation" }).click();
  await settle(page);

  await expect(page.getByText("Nobody", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Due while away").first()).toBeVisible();
  await page.getByText("Why it is affected").first().click();
  await expect(page.getByText("Arjun Rao is primary owner.").first()).toBeVisible();

  await expect(page.getByRole("heading", { name: "Who could cover?" })).toBeVisible();
  await page.getByRole("link", { name: "Simulate with Dev" }).click();
  await settle(page);
  await expect(page.getByText("Simulated").first()).toBeVisible();
  await expect(
    page.getByText("Simulation only. Nothing in the workspace was changed."),
  ).toBeVisible();

  // Real ownership is untouched: Dev is not an owner of Production deployments.
  await sidebar(page, "Responsibilities");
  await page.getByRole("link", { name: "Production deployments", exact: true }).first().click();
  await settle(page);
  const owners = page.locator("section").filter({ hasText: "Current owners" }).first();
  await expect(owners.getByText("Arjun Rao").first()).toBeVisible();
  await expect(owners.getByText("Dev Patel")).toHaveCount(0);
});

test("handover copilot: cited answer, honest not-found, history link", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto(overview);
  await sidebar(page, "Cases");
  await page
    .getByRole("link", { name: /Arjun Rao is leaving Platform/ })
    .filter({ visible: true })
    .first()
    .click();
  await settle(page);
  await page
    .getByRole("link", { name: "Capsules", exact: true })
    .filter({ visible: true })
    .first()
    .click();
  await settle(page);
  await page.getByRole("link", { name: /^For / }).filter({ visible: true }).first().click();
  await settle(page);
  await expect(page.getByRole("heading", { name: "What you now own" })).toBeVisible();

  const copilot = page.getByRole("region", { name: "Ask about this handover" });
  await copilot.getByLabel("Your question").fill("How should I deploy payments-api?");
  await copilot.getByRole("button", { name: "Ask" }).click();
  await expect(
    copilot
      .getByText(/Answer from the evidence|Search results, not an answer|Not in the evidence/)
      .first(),
  ).toBeVisible({ timeout: 90_000 });

  await copilot.getByLabel("Your question").fill("What is the zebra quokka escalation code?");
  await copilot.getByRole("button", { name: "Ask" }).click();
  await expect(copilot.getByText("Not in the evidence").last()).toBeVisible({ timeout: 90_000 });

  await page.getByRole("link", { name: "Open memory replay" }).first().click();
  await page.waitForURL(/\/timeline$/);
});
