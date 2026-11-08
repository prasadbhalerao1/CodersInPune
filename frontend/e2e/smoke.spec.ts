import { expect, type Page, test } from "@playwright/test";

// Real-account journey (local only; see playwright.config.ts). Creates its own workspace,
// so it never touches existing data.

const stamp = Date.now().toString(36);
const names = {
  workspace: `E2E ${stamp}`,
  leaving: `Lena ${stamp}`,
  joining: `Jo ${stamp}`,
  duty: `Payments on-call ${stamp}`,
};

async function submitAndSettle(page: Page, button: string) {
  await page.getByRole("button", { name: button, exact: true }).first().click();
  await page.waitForLoadState("networkidle");
}

test.describe.configure({ mode: "serial" });

let base = "";

test("create a workspace", async ({ page }) => {
  await page.goto("/workspaces");
  await page.getByLabel("Workspace name").fill(names.workspace);
  await page.getByRole("button", { name: "Create workspace" }).click();
  await page.waitForURL(/\/w\/[0-9a-f-]{36}$/);
  base = new URL(page.url()).pathname;
  await expect(page.getByRole("heading", { name: names.workspace })).toBeVisible();
});

test("add people and a responsibility with an owner, and see the risk", async ({ page }) => {
  await page.goto(`${base}/people`);
  for (const person of [names.leaving, names.joining]) {
    await page.getByLabel("Name", { exact: true }).fill(person);
    await submitAndSettle(page, "Add person");
    await expect(page.getByText(person, { exact: true })).toBeVisible();
  }

  await page.goto(`${base}/responsibilities/new`);
  await page.getByLabel("Name").fill(names.duty);
  await page
    .getByRole("button", { name: /create|save/i })
    .first()
    .click();
  await page.waitForURL(/\/responsibilities\/[0-9a-f-]{36}$/);

  const assign = page
    .locator("form")
    .filter({ has: page.getByRole("button", { name: "Assign", exact: true }) });
  await assign.getByLabel("Person or team").selectOption({ label: names.leaving });
  await assign.getByLabel("Role").selectOption("primary");
  await assign.getByRole("button", { name: "Assign", exact: true }).click();
  await page.waitForLoadState("networkidle");
  await expect(page.getByText(names.leaving).first()).toBeVisible();

  // Knowledge: capture a procedure on the responsibility, then find it by search.
  await page.getByText("+ Add knowledge").click();
  await page.getByLabel("Title", { exact: true }).fill(`Runbook ${stamp}`);
  await page.getByLabel("Content").fill("Rotate the webhook secret, then redeploy.");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText(`Runbook ${stamp}`)).toBeVisible();
  await page.goto(`${base}/knowledge?q=webhook+secret`);
  await expect(page.getByText(`Runbook ${stamp}`)).toBeVisible();

  await page.goto(`${base}/risks`);
  await expect(page.getByText("No backup").first()).toBeVisible();
});

test("run a transfer case end to end and verify the ownership change", async ({ page }) => {
  await page.goto(`${base}/cases/new?type=transfer`);
  await page.getByLabel("Title").fill(`Handover ${stamp}`);
  await submitAndSettle(page, "Create case");
  await page.waitForURL(/\/cases\/[0-9a-f-]{36}$/);
  const caseUrl = page.url();

  await page.getByLabel("Add responsibility").selectOption({ label: names.duty });
  await submitAndSettle(page, "Add");
  await page.getByLabel("Recipient", { exact: true }).selectOption({ label: names.joining });
  await submitAndSettle(page, "Save");

  // The responsibility's runbook is surfaced in the case; record that it was handed over.
  await page.getByRole("button", { name: "Mark handed over" }).click();
  await expect(page.getByText("Handed over", { exact: true })).toBeVisible();

  await page.getByLabel("New task").fill("Walk through the runbook");
  await submitAndSettle(page, "Add task");

  await submitAndSettle(page, "Submit for approval");
  await page.getByRole("button", { name: /^Approve v\d+$/ }).click();
  await page.waitForLoadState("networkidle");
  await submitAndSettle(page, "Execute handover");

  // Complete the task (the checkbox button), then meet every readiness check.
  await page.getByRole("button", { name: "Complete Walk through the runbook" }).click();
  await expect(page.getByRole("button", { name: "Reopen Walk through the runbook" })).toBeVisible();
  const checks = page.getByLabel(/^Status for /);
  for (let i = 0; i < (await checks.count()); i++) {
    const form = page.locator("form").filter({ has: checks.nth(i) });
    await checks.nth(i).selectOption("met");
    await form.getByRole("button", { name: "Set" }).click();
    await page.waitForLoadState("networkidle");
  }
  await expect(page.getByRole("status")).toContainText("Readiness is complete");
  await page.getByRole("button", { name: "Complete case" }).click();
  await expect(page.getByRole("status")).toContainText("Completed", { timeout: 15_000 });
  await page.goto(caseUrl);
  await expect(page.getByText("Case completed").first()).toBeVisible();

  await page.goto(`${base}/responsibilities`);
  const row = page.getByRole("row", { name: new RegExp(names.duty) });
  await expect(row).toContainText(names.joining);
});

test("another workspace cannot be reached", async ({ page }) => {
  // Streamed pages send their status before notFound() runs, so assert what renders.
  await page.goto("/w/00000000-0000-7000-8000-000000000000");
  await expect(page.getByText("you don't have access to it")).toBeVisible();
  await expect(page.getByText(names.duty)).toHaveCount(0);
  await expect(page.getByText(names.workspace)).toHaveCount(0);
});
