import { expect, type Page, test } from "@playwright/test";

// Real-account journey (local only; see playwright.config.ts). Creates its own workspace,
// so it never touches existing data.

const stamp = Date.now().toString(36);
const names = {
  workspace: `E2E ${stamp}`,
  leaving: `Lena ${stamp}`,
  joining: `Jo ${stamp}`,
  duty: `Payments on-call ${stamp}`,
  dept: `Finance ${stamp}`,
  team: `Billing ${stamp}`,
  orphan: `Vendor portal ${stamp}`,
};

async function submitAndSettle(page: Page, button: string) {
  await page.waitForLoadState("networkidle"); // a click before hydration is lost
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
    // Names also appear as options in the "Reports to" pickers; check the visible row.
    await expect(
      page.getByText(person, { exact: true }).filter({ visible: true }).first(),
    ).toBeVisible();
  }

  await page.goto(`${base}/responsibilities/new`);
  await page.getByLabel("Name").fill(names.duty);
  await page.getByRole("button", { name: "Create responsibility", exact: true }).click();
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
  await expect(page.getByText(`Runbook ${stamp}`).first()).toBeVisible();
  await page.goto(`${base}/knowledge?q=webhook+secret`);
  await expect(page.getByText(`Runbook ${stamp}`).first()).toBeVisible();

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
  await page.goto(`${caseUrl}?tab=knowledge`);
  await page.getByRole("button", { name: "Mark handed over" }).click();
  await expect(page.getByText("Handed over", { exact: true })).toBeVisible();

  await page.goto(`${caseUrl}?tab=tasks`);
  await page.getByText("Add a task", { exact: true }).click();
  await page.getByLabel("Title", { exact: true }).fill("Walk through the runbook");
  await submitAndSettle(page, "Add task");
  await expect(page.getByRole("link", { name: "Walk through the runbook" })).toBeVisible();

  await submitAndSettle(page, "Submit for approval");
  await expect(page.getByRole("status").first()).toContainText("Waiting for approval");
  await page.goto(`${caseUrl}?tab=approvals`);
  await page.getByRole("button", { name: /^Approve v\d+$/ }).click();
  await expect(page.getByRole("status").first()).toContainText("ready");
  await submitAndSettle(page, "Execute handover");
  await expect(page.getByRole("status").first()).toContainText("Readiness");

  // Complete the task (the checkbox button), then meet every readiness check.
  await page.goto(`${caseUrl}?tab=tasks`);
  await page.getByRole("button", { name: "Complete Walk through the runbook" }).click();
  await expect(
    page.getByRole("button", { name: "Complete Walk through the runbook" }),
  ).toBeDisabled();
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
  await page.goto(`${caseUrl}?tab=activity`);
  await expect(page.getByText("Case completed").first()).toBeVisible();

  await page.goto(`${base}/responsibilities`);
  const row = page.getByRole("row", { name: new RegExp(names.duty) });
  await expect(row).toContainText(names.joining);
});

test("temporary coverage: plan, cover, briefing, early return", async ({ page }) => {
  const local = (d: Date) =>
    new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
  await page.goto(`${base}/cases/new?type=coverage`);
  await page.getByLabel("Title").fill(`Leave ${stamp}`);
  await page.getByLabel("Who is away").selectOption({ label: names.joining });
  await page.locator("#starts").fill(local(new Date(Date.now() - 60_000)));
  await page.locator("#ends").fill(local(new Date(Date.now() + 7 * 86_400_000)));
  await submitAndSettle(page, "Create case");
  await page.waitForURL(/\/cases\/[0-9a-f-]{36}$/);
  const caseUrl = page.url();

  // The ownership plan explains who owns it now and what happens during and after cover.
  const plan = page
    .getByRole("region", { name: "Ownership plan" })
    .or(page.locator("section").filter({ hasText: "Ownership plan" }));
  await expect(plan.first()).toContainText("Nobody covers yet");
  await page.getByLabel("Covered by", { exact: true }).selectOption({ label: names.leaving });
  await submitAndSettle(page, "Save");
  await expect(plan.first()).toContainText("back in charge");

  await submitAndSettle(page, "Submit for approval");
  await expect(page.getByRole("status").first()).toContainText("Waiting for approval");
  await page.goto(`${caseUrl}?tab=approvals`);
  await page.getByRole("button", { name: /^Approve v\d+$/ }).click();
  await expect(page.getByRole("status").first()).toContainText("ready");
  await submitAndSettle(page, "Execute handover");
  await expect(page.getByRole("status").first()).toContainText("Readiness");
  await page.goto(caseUrl);
  await expect(plan.first()).toContainText("covering until");

  await page.getByRole("link", { name: /review the return briefing/i }).click();
  await page.waitForURL(/\/briefing$/);
  await expect(page.getByText("Cover is still running").first()).toBeVisible();
  await expect(page.getByText("What was covered").first()).toBeVisible();
  await expect(page.getByText(names.duty).first()).toBeVisible();

  await page.goto(`${caseUrl}?tab=tasks`);
  const checks = page.getByLabel(/^Status for /);
  await expect(checks.first()).toBeVisible();
  for (let i = 0; i < (await checks.count()); i++) {
    const form = page.locator("form").filter({ has: checks.nth(i) });
    await checks.nth(i).selectOption("met");
    await form.getByRole("button", { name: "Set" }).click();
    await page.waitForLoadState("networkidle");
  }
  await page.getByRole("button", { name: "End coverage early" }).click();
  await expect(page.getByRole("status").first()).toContainText("Completed", { timeout: 15_000 });
  await page.goto(`${base}/responsibilities`);
  await expect(page.getByRole("row", { name: new RegExp(names.duty) })).toContainText(
    names.joining,
  );
});

test("command menu: search, open, and quick-create a person", async ({ page }) => {
  await page.goto(base);
  await page.waitForLoadState("networkidle"); // the shortcut is wired after hydration
  await page.keyboard.press("Control+k");
  const menu = page.getByRole("dialog", { name: "Search and commands" });
  await expect(menu).toBeVisible();
  await menu.getByRole("combobox").fill(names.duty.slice(0, 12));
  // The responsibility and its risk both match; responsibilities are listed first.
  await expect(menu.getByRole("option").first()).toContainText(names.duty);
  await expect(menu.getByText("Risks", { exact: true })).toBeVisible();
  await page.keyboard.press("Enter");
  await page.waitForURL(/\/responsibilities\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: names.duty })).toBeVisible();

  await page.keyboard.press("Control+k");
  await menu.getByRole("combobox").fill("add person");
  await menu.getByRole("option", { name: "Add person" }).click();
  await menu.getByLabel("Name").fill(`Quinn ${stamp}`);
  await menu.getByRole("button", { name: "Create" }).click();
  await page.waitForURL(/\/people\/[0-9a-f-]{36}$/);
  await expect(page.getByText(`Quinn ${stamp}`).first()).toBeVisible();
  await expect(page.getByText("No ownership roles")).toBeVisible();
});

test("insights, automations, policies and integrations render for an owner", async ({ page }) => {
  await page.goto(`${base}/insights`);
  await expect(page.getByText("Continuity Debt").first()).toBeVisible();
  await expect(page.getByText("Open ownership risks").first()).toBeVisible();

  await page.goto(`${base}/automations`);
  await expect(page.getByText("Critical responsibility without a backup").first()).toBeVisible();

  await page.goto(`${base}/settings`);
  const days = page.getByLabel("Knowledge review interval (days)");
  await days.fill("60");
  await submitAndSettle(page, "Save policies");
  await page.reload();
  await expect(page.getByLabel("Knowledge review interval (days)")).toHaveValue("60");

  for (const provider of ["linear", "notion"]) {
    await page.goto(`${base}/integrations/${provider}`);
    await expect(page.getByRole("navigation", { name: "Integrations" })).toBeVisible();
  }
});

test("catalogue: departments, teams and an unowned responsibility", async ({ page }) => {
  await page.goto(`${base}/people`);
  await page.getByLabel("Department name").fill(names.dept);
  await submitAndSettle(page, "Add");
  await expect(page.getByRole("link", { name: new RegExp(names.dept) }).first()).toBeVisible();

  await page.getByLabel("Team name").fill(names.team);
  await submitAndSettle(page, "Add team");
  await expect(page.getByText(names.team, { exact: true }).first()).toBeVisible();

  await page.goto(`${base}/responsibilities/new`);
  await page.getByLabel("Name").fill(names.orphan);
  await page.getByRole("button", { name: "Create responsibility", exact: true }).click();
  await page.waitForURL(/\/responsibilities\/[0-9a-f-]{36}$/);
  await page.goto(`${base}/responsibilities`);
  await expect(page.getByRole("row", { name: new RegExp(names.orphan) })).toBeVisible();
});

test("operations: an automation alerts the inbox and records its run", async ({ page }) => {
  await page.goto(`${base}/automations`);
  const rule = page
    .getByRole("listitem")
    .filter({ hasText: "Responsibility without a primary owner" });
  await rule.getByLabel("Enabled").check();
  await rule.getByRole("button", { name: "Save", exact: true }).click();
  await page.waitForLoadState("networkidle");

  // The run happens in the background worker; wait for its alert to reach the inbox.
  await expect(async () => {
    await page.goto(`${base}/inbox`);
    await expect(page.getByText("Responsibility has no primary owner").first()).toBeVisible({
      timeout: 2000,
    });
  }).toPass({ timeout: 45_000 });
  await page.getByText("Responsibility has no primary owner").first().click();
  await page.waitForURL(/\/responsibilities\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: names.orphan })).toBeVisible();

  await page.goto(`${base}/automations`);
  const ran = page
    .getByRole("listitem")
    .filter({ hasText: "Responsibility without a primary owner" });
  await expect(ran.getByText("Last run OK")).toBeVisible();
  await ran.getByText(/Execution history/).click();
  await expect(ran.getByRole("cell", { name: "Schedule" }).first()).toBeVisible();
});

test("the shell names the workspace and navigates on a phone", async ({ page }) => {
  await page.goto(base);
  const sidebar = page.getByRole("complementary", { name: "Primary" });
  await expect(sidebar.getByText(names.workspace)).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(base);
  await expect(sidebar).toBeHidden();
  await page.locator("summary:visible").filter({ hasText: names.workspace }).click();
  await page
    .getByRole("navigation", { name: "Workspace" })
    .getByRole("link", { name: "Cases" })
    .click();
  await page.waitForURL(/\/cases$/);
});

test("another workspace cannot be reached", async ({ page }) => {
  // Streamed pages send their status before notFound() runs, so assert what renders.
  await page.goto("/w/00000000-0000-7000-8000-000000000000");
  await expect(page.getByText("you don't have access to it")).toBeVisible();
  await expect(page.getByText(names.duty)).toHaveCount(0);
  await expect(page.getByText(names.workspace)).toHaveCount(0);
});

test("help explains the product and links back into it", async ({ page }) => {
  await page.goto(`${base}/help`);
  await expect(page.getByRole("heading", { name: "Help" })).toBeVisible();
  await page.getByRole("link", { name: /Review risks/ }).click();
  await page.waitForURL(/\/risks$/);
});

// Last: it leaves this run's workspace scheduled for deletion, so test data is purged.
test("deleting a workspace needs its exact name and can be cancelled", async ({ page }) => {
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto(`${base}/settings/data`);
  const confirmName = page.getByLabel(/to confirm/);
  const banner = page.getByText(/will be permanently deleted on/);

  await confirmName.fill("not the name");
  await submitAndSettle(page, "Delete workspace");
  await expect(page.getByText("Type the workspace name exactly to confirm.")).toBeVisible();
  await expect(banner).toHaveCount(0);

  await confirmName.fill(names.workspace);
  await submitAndSettle(page, "Delete workspace");
  await expect(banner).toBeVisible();

  await submitAndSettle(page, "Cancel deletion");
  await expect(banner).toHaveCount(0);

  await page.getByLabel(/to confirm/).fill(names.workspace);
  await submitAndSettle(page, "Delete workspace");
  await expect(banner).toBeVisible();
});
