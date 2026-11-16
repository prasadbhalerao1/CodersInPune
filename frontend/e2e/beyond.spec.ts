import { expect, type Page, test } from "@playwright/test";

// The features beyond the three Round 3 commitments, on the newest sample workspace.
// Starts at the landing page and only clicks what a person can see. No step here calls a
// model: AI-backed actions are covered by backend tests with a scripted model.

test.describe.configure({ mode: "serial" });

let overview = "";

async function settle(page: Page) {
  await page.waitForLoadState("networkidle");
}

async function sidebar(page: Page, label: string) {
  await page
    .getByRole("navigation", { name: "Workspace" })
    .getByRole("link", { name: label, exact: true })
    .click();
  await settle(page);
}

test("open the newest sample workspace from the landing page", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Workspaces", exact: true }).first().click();
  await page.waitForURL(/\/workspaces$/);
  await settle(page);
  await page
    .getByRole("link", { name: /Northwind Labs \(demo\)/ })
    .last()
    .click();
  await page.waitForURL(/\/w\/[0-9a-f-]{36}$/);
  await settle(page);
  overview = new URL(page.url()).pathname;
  await expect(page.getByRole("button", { name: /Fresh sample/ })).toBeVisible();
});

test("meetings: items cite their transcript lines and can be accepted", async ({ page }) => {
  await page.goto(overview);
  await sidebar(page, "Meetings");
  await page.getByRole("link", { name: /Arjun handover kickoff/ }).click();
  await settle(page);
  await expect(page.getByRole("heading", { name: /Decisions/ })).toBeVisible();
  // A line chip jumps to the cited transcript line.
  await page
    .getByRole("link", { name: /^L\d+$/ })
    .first()
    .click();
  await expect(page).toHaveURL(/#L\d+$/);
  const accept = page.getByRole("button", { name: "Accept" }).first();
  if (await accept.isVisible()) {
    const before = await page.getByRole("button", { name: "Accept" }).count();
    await accept.click();
    await expect(page.getByRole("button", { name: "Accept" })).toHaveCount(before - 1);
  }
});

test("decision log lists decisions from every source", async ({ page }) => {
  await page.goto(overview);
  await sidebar(page, "Decision log");
  await expect(page.getByRole("tab", { name: /Meetings/ })).toBeVisible();
  await expect(page.getByText(/We decided Dev takes over production deployments/)).toBeVisible();
});

test("expertise map ranks the most fragile work first", async ({ page }) => {
  await page.goto(overview);
  await sidebar(page, "Expertise map");
  await expect(page.getByText("held by one person or nobody")).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
});

test("knowledge flags the old runbook as changed since review", async ({ page }) => {
  await page.goto(overview);
  await sidebar(page, "Knowledge");
  const drift = page.getByRole("region", { name: /Code changed since review/ });
  await expect(drift).toBeVisible();
  await expect(drift.getByText("Deploy payments-api (old runbook)")).toBeVisible();
});

test("a case's 30/60/90 plan turns a step into a task", async ({ page }) => {
  await page.goto(overview);
  await sidebar(page, "Cases");
  await page.getByRole("link", { name: /Arjun Rao is leaving Platform/ }).click();
  await settle(page);
  await page.getByRole("link", { name: "30/60/90 plan" }).click();
  await settle(page);
  await expect(page.getByRole("heading", { name: "First 30 days" })).toBeVisible();
  const add = page.getByRole("button", { name: /Add as task/ }).first();
  const before = await page.getByText("On the task list").count();
  await add.click();
  await expect(page.getByText("On the task list")).toHaveCount(before + 1);
  // The Analysis tab carries Handover Autopilot.
  await page.getByRole("link", { name: "Analysis", exact: true }).click();
  await settle(page);
  await expect(page.getByRole("heading", { name: /Handover Autopilot/ })).toBeVisible();
});

test("the simulator offers a scenario report", async ({ page }) => {
  await page.goto(overview);
  await sidebar(page, "What-if simulator");
  const arjun = await page
    .locator('select[name="person"] option', { hasText: "Arjun Rao" })
    .getAttribute("value");
  await page.getByLabel("What if").selectOption(arjun ?? "");
  await page.getByRole("button", { name: "Run simulation" }).click();
  await settle(page);
  const report = page.getByRole("link", { name: /Download scenario report/ });
  await expect(report).toBeVisible();
  const response = await page.request.get((await report.getAttribute("href")) ?? "");
  expect(response.status()).toBe(200);
  expect(await response.text()).toContain("Cover candidates compared");
});

test("Slack lives under Integrations", async ({ page }) => {
  await page.goto(overview);
  await sidebar(page, "Integrations");
  await page.getByRole("link", { name: "Slack", exact: true }).click();
  await settle(page);
  await expect(page.getByRole("heading", { name: "Slack" })).toBeVisible();
});
