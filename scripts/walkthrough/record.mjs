// Records the judges' walkthrough as one continuous take: starts at the landing page and
// only clicks what a person can see. The script is a list of beats; each beat is one or two
// sentences of narration plus the actions they describe. A beat starts its actions as its
// sentence starts, and the next beat waits until the sentence has finished, so the voice
// always describes what is on screen. Every beat's start time is written out for the mix.
//
// Usage (from the repo root, app running locally, signed-in session saved by the e2e setup):
//   node scripts/walkthrough/record.mjs --list > scripts/walkthrough/narration.json
//   python scripts/walkthrough/voice.py scripts/walkthrough/narration.json <voiceDir>
//   node scripts/walkthrough/record.mjs <outDir> <voiceDir>/timing.json
// A ^ in a sentence marks a cue word: the beat's actions start just before it is spoken,
// so the click lands on the word; an action can wait for later cues with cue(n).
import { spawn } from "node:child_process";
import { appendFileSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";

const BASE = process.env.RELAY_BASE_URL ?? "http://localhost:3000";
const LIST = process.argv[2] === "--list";

// ---------------------------------------------------------------- browser helpers
let page;
let cursor = { x: 800, y: 450 };
const pause = (ms) => page.waitForTimeout(ms);
const settle = () => page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => {});
const visible = (loc) => loc.filter({ visible: true }).first();

// Moves like a hand: eases in and out along a slight curve instead of a straight, even glide.
async function moveTo(x, y) {
  const from = cursor;
  const steps = Math.max(14, Math.round(Math.hypot(x - from.x, y - from.y) / 16));
  const bend = 0.12 * (Math.random() < 0.5 ? 1 : -1);
  const cx = (from.x + x) / 2 + (y - from.y) * bend;
  const cy = (from.y + y) / 2 - (x - from.x) * bend;
  for (let i = 1; i <= steps; i++) {
    const t = i / steps;
    const e = t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
    const px = (1 - e) ** 2 * from.x + 2 * (1 - e) * e * cx + e * e * x;
    const py = (1 - e) ** 2 * from.y + 2 * (1 - e) * e * cy + e * e * y;
    await page.mouse.move(px, py);
    await page.waitForTimeout(10);
  }
  cursor = { x, y };
}
async function point(loc) {
  const el = visible(loc);
  await el.scrollIntoViewIfNeeded();
  await pause(250);
  const box = await el.boundingBox();
  if (!box) throw new Error("no box");
  await moveTo(box.x + Math.min(box.width / 2, 120), box.y + Math.min(box.height / 2, 40));
  return el;
}
async function click(loc, after = 900) {
  const el = await point(loc);
  await pause(250);
  await el.click();
  await pause(after);
  await settle();
}
async function type(loc, text) {
  await click(loc, 200);
  await page.keyboard.type(text, { delay: 35 });
  await pause(400);
}
async function hover(loc, ms = 1200) {
  await point(loc);
  await pause(ms);
}
async function scroll(pixels, stepMs = 40) {
  const step = pixels > 0 ? 60 : -60;
  for (let done = 0; Math.abs(done) < Math.abs(pixels); done += step) {
    await page.mouse.wheel(0, step);
    await pause(stepMs);
  }
  await pause(400);
}
async function scrollToTop() {
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await page.locator("main").first().evaluate((m) => m.scrollTo?.({ top: 0, behavior: "smooth" }));
  await pause(900);
}
const browse = async (n = 4, px = 300) => {
  for (let i = 0; i < n; i++) await scroll(px, 50);
};
const link = (name) => page.getByRole("link", { name });
const button = (name) => page.getByRole("button", { name });
const heading = (name) => page.getByRole("heading", { name });
const sidebar = (label) =>
  click(page.getByRole("navigation", { name: "Workspace" }).getByRole("link", { name: label, exact: true }));
const caseTab = (name) =>
  click(page.getByRole("navigation", { name: "Case sections" }).getByRole("link", { name }), 2000);
const subnav = (nav, name) =>
  click(page.getByRole("navigation", { name: nav }).getByRole("link", { name, exact: true }), 2000);

// Slow work (AI answers, creating the sample) runs in the background while the next
// sentences talk about something useful; a later beat waits for it with ready().
let pending = Promise.resolve();
const background = (work) => { pending = work.catch(() => {}); };
const ready = () => pending;

const copilot = () => page.getByRole("region", { name: "Ask about this handover" });
const lastAnswer = () => copilot().getByRole("article").last();
async function ask(question) {
  const before = await copilot().getByRole("article").count();
  await type(copilot().getByLabel("Your question"), question);
  await click(copilot().getByRole("button", { name: "Ask" }), 500);
  background(page
    .waitForFunction(
      ([n]) => {
        const all = document.querySelectorAll('section[aria-labelledby="copilot-heading"] article');
        return all.length > n && /Answer from the evidence|Not in the evidence|Search results/.test(all[all.length - 1].textContent ?? "");
      },
      [before],
      { timeout: 90_000 },
    ));
}

// ---------------------------------------------------------------- the script
// [chapter caption, [[sentence, actions?], ...]]
const SCRIPT = [
  ["Relay", [
    ["Good evening, judges. We are team Midnight Ciphers, and this is Relay. Picture this. It's Friday afternoon, and Arjun, the engineer who runs your production deployments, hands in his notice. Who else knows how to roll back a bad release? Where is the runbook, and is it still right? Which decisions did he make that nobody wrote down? In most companies the honest answer is: nobody is sure.",
      async () => { await pause(1500); await hover(page.getByRole("heading", { level: 1 }), 2000); }],
    ["That is the problem statement we were given: knowledge handover. Work and knowledge are spread across documents, tickets, repositories, runbooks and people's heads, and no system holds them in one current, permission-aware place. Our landing page names the three ways it fails: a single owner, scattered context, and unclear handovers.",
      async () => { await scroll(420, 50); await hover(page.getByText("Single owner", { exact: true }), 1500); await hover(page.getByText("Scattered context", { exact: true }), 1500); await hover(page.getByText("Unclear handovers", { exact: true }), 1500); }],
    ["In practice that means: a new owner does not know what they inherited. A departing person's knowledge is never captured. A short absence leaves tasks and escalations hanging. Critical work has no backup. Projects move without their decisions and risks. Documentation is stale, contradictory or unowned. A manager cannot tell whether a handover is really complete. Single-person dependencies are found only after something breaks. And a generic AI assistant writes a confident summary without proving that any of it is current, or something the reader may see."],
    ["So we built Relay, an organisational continuity platform. It knows who is accountable for what, rebuilds the context behind that work from GitHub, Linear and Notion with cited evidence, forecasts what an absence would break before it happens, moves ownership through a reviewed, audited handover, and then checks that the handover actually took hold.",
      () => scrollToTop()],
    ["Over the next twenty minutes, I'll use every feature live, exactly as a new user would, with no cuts and no slides, and you'll see each of those failures handled. As I go, I'll name where each feature lives, so you can retrace every step yourselves."],
  ]],
  ["Landing page", [
    ["As I scroll down, the landing page plays the whole loop as an interactive walkthrough. It starts when something changes: a person leaves, goes on leave, or changes team.",
      async () => { await scroll(520, 50); await pause(1500); }],
    ["Step two, ^evidence, not guesses: Relay gathers evidence instead of guesses, from the tools the team already uses.",
      () => click(button("Evidence, not guesses"), 1500)],
    ["Step three, ^people decide. A manager reviews and approves the plan; nothing moves on its own.",
      () => click(button("People decide"), 1500)],
    ["Step four, ^a handover that fits: it's written for the person receiving it.",
      () => click(button("A handover that fits"), 1500)],
    ["And step five, ^ownership moves, with a full record of who held what, and when.",
      () => click(button("Ownership moves"), 1500)],
    ["Further down are the product areas: the responsibility catalogue, continuity cases, evidence-backed analysis, handover capsules, governed knowledge, and read-only connections.",
      () => browse(4, 300)],
    ["And the trust section. AI only drafts proposals and never holds a tool that can change data. Every workspace is isolated by Postgres row-level security. And gaps in the sources are shown as gaps, never filled in by a model.",
      () => browse(4, 300)],
    ["The public pages also publish a robots file, a sitemap, an llms dot t x t file and structured data, so search engines and AI agents can understand what Relay is. Now, let's go in.",
      () => scrollToTop()],
  ]],
  ["Sign in and the sample workspace", [
    ["I'll click ^Go to your workspaces. Sign-in uses WorkOS with a one-time email code, so Relay never stores a password, and signing in grants access to nothing until you are a member of a workspace.",
      async () => { await click(link("Go to your workspaces →"), 1500); await page.waitForURL(/\/workspaces$/); }],
    ["Here I can create an empty workspace for my own data, or a sample one. I'll click ^Create sample workspace: Northwind Labs, a fictional company with eight people, seven responsibilities and a year of synthetic GitHub, Linear and Notion history, where one engineer, Arjun Rao, is leaving.",
      async () => {
        await hover(button("Create sample workspace"), 1500);
        await click(button("Create sample workspace"), 500);
        const limited = page.getByRole("alert").filter({ hasText: /several sample workspaces/ });
        background((async () => {
          await Promise.race([
            page.waitForURL(/\/w\/[0-9a-f-]{36}$/, { timeout: 90_000 }).catch(() => {}),
            limited.waitFor({ timeout: 90_000 }).catch(() => {}),
          ]);
          if (await limited.isVisible()) {
            await click(page.getByRole("link", { name: /Northwind Labs \(demo\)/ }).last(), 1000);
            await page.waitForURL(/\/w\/[0-9a-f-]{36}$/);
          }
          await settle();
        })());
      }],
    ["While it builds, one architectural decision we made on day one. The server never trusts the browser to say which workspace it is in; the workspace comes only from your membership. Then Postgres itself enforces the boundary with forced row-level security, and the app connects as a restricted role that cannot bypass it. So even a buggy query cannot read another company's data, and our test suite attacks exactly that.",
      () => ready()],
  ]],
  ["Overview", [
    ["We land on the Overview, the first item in the left sidebar. Because product guidance is on, Relay offers a short tour and a setup checklist. Each item is computed from real records; a connected tool only counts once its first sync has finished.",
      async () => { const start = page.getByRole("region", { name: "Getting started" }); if (await start.isVisible()) await hover(start, 2000); }],
    ["Continuity health is the share of critical work that has an owner, a backup and current knowledge, next to the continuity debt score.",
      () => hover(page.getByLabel("Continuity health"), 2500)],
    ["Below are the counts: active responsibilities, work with no primary owner, critical work with no backup, and open risks. Needs attention lists every gap with the rule that raised it.",
      () => browse(3)],
    ["Then the handovers in motion, the top risks, and recent ownership changes. Every number links to the records behind it, so in ten seconds a manager knows where the organisation is fragile.",
      async () => { await browse(4); await scrollToTop(); }],
  ]],
  ["Learn Relay: guidance and tours", [
    ["For new users, there's ^Learn Relay in the sidebar. The product guidance switch is personal: turning it off hides automatic tips and the checklist, but every tutorial keeps working.",
      async () => { await sidebar("Learn Relay"); await hover(page.getByRole("switch", { name: "Product guidance" }), 1500); }],
    ["There are eight tours, and each unlocks only when the workspace has the data it shows, so nobody is sent into an empty screen. ^Restart tutorial progress clears only the tours, never workspace data.",
      () => click(button("Restart tutorial progress"), 1500)],
    ["Let me ^start the first tour. It highlights the real element on the page and explains it.",
      async () => {
        const basics = page.getByRole("listitem").filter({ hasText: "Find your way around" });
        await click(basics.getByRole("link", { name: /Start|Resume|Replay/ }), 2000);
      }],
    ["I can go ^forward step by step,",
      async () => { const d = page.getByRole("dialog"); for (let i = 0; i < 2; i++) await click(d.getByRole("button", { name: "Next" }), 2500); }],
    ["go ^back,",
      () => click(page.getByRole("dialog").getByRole("button", { name: "Back" }), 1500)],
    ["and finish. If I leave a tour halfway, it resumes exactly where I stopped, and I can replay it later.",
      async () => {
        const d = page.getByRole("dialog");
        for (let i = 0; i < 6 && !(await d.getByRole("button", { name: "Done" }).isVisible()); i++) {
          await click(d.getByRole("button", { name: "Next" }), 1200);
        }
        await click(d.getByRole("button", { name: "Done" }), 1000);
      }],
  ]],
  ["My Work and Inbox", [
    ["^My Work, in the sidebar, is each person's single list: handovers addressed to me, knowledge I'm asked to review, tasks assigned to me,",
      async () => { await sidebar("My Work"); await hover(heading("Knowledge to review"), 1500); }],
    ["and the cases I coordinate, with their open tasks and status.",
      () => hover(heading("Cases I coordinate"), 1500)],
    ["The ^Inbox collects notifications: assignments, approvals, mentions, reminders and automation alerts. It's empty for me right now; email is optional, and everything also lands here.",
      () => sidebar("Inbox")],
  ]],
  ["People, teams and departments", [
    ["^People and Teams is the directory: departments, people with their title, department, manager and GitHub login, and teams. People can be added here or imported from a spreadsheet.",
      async () => { await sidebar("People & Teams"); await hover(heading("People"), 1500); await hover(heading("Teams"), 1200); }],
    ["Let me open ^Arjun. His page shows every ownership role he holds,",
      async () => { await click(page.getByRole("link", { name: "Arjun Rao", exact: true }), 1500); await hover(heading("Ownership roles"), 1500); }],
    ["the open risks that depend on him, and the continuity cases that affect him. There is also a button to simulate his absence, which we'll use later.",
      async () => { await hover(heading("Open risks"), 1500); await hover(heading("Active continuity cases"), 1200); await hover(link("What if Arjun is unavailable?"), 1200); }],
    ["And the ^Platform team page shows the same view for a whole team: its members, roles, risks and cases.",
      async () => { await sidebar("People & Teams"); await click(page.getByRole("main").getByRole("link", { name: "Platform", exact: true }), 2000); }],
  ]],
  ["Responsibilities and ownership", [
    ["Now the heart of Relay: ^Responsibilities, in the sidebar. A responsibility is anything that must keep working, software or not. Each row shows its criticality, its primary owner and its backups.",
      async () => { await sidebar("Responsibilities"); await hover(page.locator('[data-tour="responsibility-table"]'), 2000); }],
    ["Let me open ^Production deployments. Stewardship shows when the record was last reviewed and by whom; owners confirm it on a cadence, so stale ownership becomes visible.",
      async () => { await click(page.getByRole("link", { name: "Production deployments", exact: true }), 1500); await hover(heading("Stewardship"), 1500); }],
    ["Current owners and backups, where an assignment can be ended or corrected with a reason.",
      () => hover(heading("Current owners"), 2000)],
    ["Continuity shows its risks and cases. Dependencies link it to other work and assets: depends on, feeds, escalates to, or shares access with.",
      async () => { await hover(heading("Continuity"), 1500); await hover(heading("Dependencies"), 1500); }],
    ["Then its knowledge, the assets it looks after, and the full ownership history, which is never overwritten. This one record holds what Jira, Confluence and a service catalogue each only hold a piece of.",
      async () => { await hover(heading("Knowledge"), 1200); await hover(heading("Assets"), 1200); await hover(heading("Ownership history"), 1500); await scrollToTop(); }],
  ]],
  ["Governed knowledge", [
    ["Sidebar, ^Knowledge. It holds procedures, decisions, contacts and links, each tied to a responsibility, with a steward and a review date. Anyone can confirm an item is still accurate; stewards verify or archive it. Pages imported from Notion stay unverified until a person checks them.",
      async () => { await sidebar("Knowledge"); await hover(button("Still accurate"), 2000); }],
    ["Let me open ^Deploy payments API. Relay flags a possible conflict with the old runbook, which still describes a deploy without a canary.",
      async () => { await click(page.getByRole("link", { name: "Deploy payments-api", exact: true }), 1500); await hover(heading("Possible conflicts"), 2500); }],
    ["Every edit is a version I can compare, and disputes keep their history.",
      () => hover(heading("Versions"), 2000)],
  ]],
  ["Assets", [
    ["Sidebar, ^Assets: the things work depends on, such as repositories, services, vendors, infrastructure and documents, filterable by type, lifecycle, criticality and stewardship. The Legacy SFTP bridge has nobody looking after it, which Relay raises as a risk.",
      async () => { await sidebar("Assets"); await hover(page.getByRole("link", { name: "Legacy SFTP bridge" }), 2000); }],
    ["Opening ^billing database shows its details, the work and knowledge linked to it, who looks after it, and the risks that reach it through those people.",
      async () => {
        await click(page.getByRole("link", { name: "billing-db", exact: true }), 1500);
        for (const h of ["Details", "Linked work and knowledge", "Looked after by", "Risks through its stewards"]) await hover(heading(h), 1200);
      }],
  ]],
  ["Round 3 feature 1: Project Memory Replay", [
    ["Now, the first of our three Round 3 improvements: Project Memory Replay. A successor's first week is usually spent digging through old tickets. To find it, open a ^responsibility, here Production deployments, and click Memory replay.",
      async () => {
        await sidebar("Responsibilities");
        await click(page.getByRole("link", { name: "Production deployments", exact: true }), 1200);
        await click(link("Memory replay"), 1200);
        await page.waitForURL(/\/timeline$/);
        await settle();
      }],
    ["Relay merges pull requests, issues, pages, decisions and ownership changes into one timeline. Every event is a fact with its source, and categories come from simple rules over the source data, not from a model.",
      () => browse(2)],
    ["I can filter by category. ^Incident shows the checkout outage after a payments API release.",
      async () => { await scrollToTop(); await click(page.getByRole("group", { name: "Filter by category" }).getByRole("button", { name: /Incident/ }), 2500); }],
    ["Back to ^all events, and press Replay history: the history plays forward, event by event.",
      async () => { await click(page.getByRole("group", { name: "Filter by category" }).getByRole("button", { name: /^All/ }), 1000); await click(button("Replay history"), 5000); }],
    ["I ^pause, and inspect an event: where it came from, how its category was derived, and which events it links to. Large histories load two hundred events at a time.",
      async () => { await click(button("Pause"), 1000); await click(button("Inspect"), 2500); }],
  ]],
  ["Memory Replay: AI chapters and questions", [
    ["Now, ^Explain this history. The AI groups the events into chapters on the time axis.",
      async () => {
        const explain = page.getByRole("button", { name: "Explain this history" });
        if (await explain.isVisible()) await click(explain, 500);
        // If the provider is briefly unavailable, retry like a person would.
        background((async () => {
          for (let attempt = 0; attempt < 6; attempt++) {
            await page.getByText(/Inferred ·|AI is not configured|switched off|could not answer/).first().waitFor({ timeout: 90_000 });
            const retry = page.getByRole("button", { name: "Try again" });
            if (!(await retry.isVisible())) return;
            await pause(10_000);
            await click(retry, 500);
            await page.getByText(/could not answer/).first().waitFor({ state: "hidden", timeout: 15_000 }).catch(() => {});
          }
        })());
      }],
    ["While the model works, here is how we keep it honest. It receives the events numbered, and must cite them by number. The server then checks every citation against the events this reader is allowed to see, and anything uncited or invented is removed before it reaches the screen.",
      () => ready()],
    ["And here are the chapters. Every one is labelled Inferred, because it is an interpretation, and it cites the exact events it rests on.",
      () => hover(page.getByText(/Inferred ·/).first(), 2000).catch(() => {})],
    ["I can also ^ask the history a question: why does every payments API deploy need a canary?",
      async () => {
        await type(page.getByLabel("Your question"), "Why does every payments-api deploy need a canary?");
        await click(button("Ask"), 500);
        background(page.getByText(/From the history|Search results, not an answer|Not in the history/).last().waitFor({ timeout: 90_000 }));
      }],
    ["While that runs: the question is answered from this timeline only. A member who may not see some evidence gets an answer built without it, so asking a question can never leak what a page would hide.",
      () => ready()],
    ["The answer cites the outage and the decision that introduced the canary. If the history does not record the answer, Relay says so instead of guessing.",
      () => hover(page.getByText(/From the history|Search results, not an answer|Not in the history/).last(), 2500)],
  ]],
  ["Continuity risks", [
    ["Sidebar, ^Risks. Risks are raised by explainable rules, never by a model: no backup, a backup who is the same person as the owner, a critical responsibility with a single owner, team ownership without an accountable contact, or an asset nobody looks after.",
      async () => { await sidebar("Risks"); await browse(2); await scrollToTop(); }],
    ["^Opening one shows why it is a risk, the recommended action, and the affected work. A manager can assign it, accept it with a reason, or open a case from it, and every decision is audited.",
      async () => { await click(page.locator('main a[href*="/risks/"]'), 1500); await hover(heading("Why this is a risk"), 2000); await hover(heading("Recommended action"), 2000); }],
  ]],
  ["Insights, trends and key-person exposure", [
    ["Sidebar, ^Insights, for managers and auditors; members are refused by the server. Continuity debt is a sum of explained components, each with its rule and points, so fixing an item lowers the debt by exactly its points.",
      async () => { await sidebar("Insights"); await hover(heading("Continuity Debt"), 2500); }],
    ["New this round: key-person exposure. These are the people who are the only holder of some work, ranked by criticality. If Arjun were away tomorrow, production deployments would have nobody.",
      () => hover(heading("Key-person exposure"), 3000)],
    ["Then coverage, knowledge health, and continuity operations, such as overdue tasks and the median days to close a case.",
      async () => { for (const h of ["Coverage", "Knowledge health", "Continuity operations"]) await hover(heading(h), 1200); }],
    ["^Trends saves snapshots, so you can see whether continuity is improving over thirty, ninety or one hundred eighty days, with every metric's definition shown.",
      async () => { await scrollToTop(); await click(link(/Trends/), 2000); await hover(heading("Saved snapshots"), 1500); }],
  ]],
  ["Round 3 feature 2: What If? simulator", [
    ["Back on ^Insights, one click on What if Arjun is away opens our second improvement, the What If simulator. Instead of discovering the gap after someone leaves, a manager sees it today, while there is still time to act.",
      async () => { await sidebar("Insights"); await click(link("What if Arjun is away?"), 1500); }],
    ["I set Arjun as unavailable for ^two weeks, and run the simulation.",
      async () => {
        await click(page.getByLabel("is unavailable for"), 300);
        await page.getByLabel("is unavailable for").selectOption({ label: "2 weeks" });
        await pause(600);
        await click(button("Run simulation"), 2000);
      }],
    ["Production deployments is left with nobody, readiness drops, and open work that falls due while he is away is listed.",
      async () => { await hover(page.getByText("Nobody", { exact: true }), 2000); await hover(page.getByText("Due while away"), 1500); }],
    ["Every result explains ^why it is affected; here, Arjun Rao is primary owner.",
      () => click(page.getByText("Why it is affected"), 2000)],
    ["This is a deliberate design choice: there is no AI model in this forecast. It replays the same ownership rules that raise real risks, on an in-memory copy, and writes nothing. So the same question always gives the same, explainable answer."],
  ]],
  ["What If?: who could cover", [
    ["Below is Who could cover. Candidates come from recorded links: the planned recipient, an existing role, the same team or department. Each one is simulated with the same rules and compared with nobody stepping in.",
      async () => { await hover(heading("Who could cover?"), 2000); await scroll(300, 50); }],
    ["Anyone who would carry far more than the team's typical load is flagged as would be overloaded. The rule is explicit, not learned: their load after cover is at least double the typical load, and at least three items more. Here, nobody crosses that line.",
      () => pause(1500)],
    ["Let me ^simulate with Dev, the planned recipient. The gap closes and readiness rises, and the banner confirms nothing in the workspace changed.",
      async () => { await click(link("Simulate with Dev"), 2000); await hover(page.getByText("Simulation only. Nothing in the workspace was changed."), 2000); }],
    ["And ^Plan a real handover turns this scenario into a real case form: a temporary coverage case, with Arjun already filled in. Creating it is a separate, audited step.",
      async () => { await click(link("Plan a real handover"), 2000); await hover(page.getByLabel("Title"), 1500); }],
  ]],
  ["Continuity cases", [
    ["In the sidebar, ^Cases lists every handover. Relay supports onboarding, transfer, temporary coverage, departure and project handover cases. I'll open Arjun's departure.",
      async () => { await sidebar("Cases"); await click(link(/Arjun Rao is leaving Platform/), 1500); }],
    ["A case moves through an explicit state model: scope, plan and approve, hand over, and complete. The progress bar and next step always say what to do now, and blockers show who must resolve them.",
      () => hover(heading("Blockers"), 2500)],
    ["The ownership plan shows, for each responsibility, who holds it now, who receives it, and when it moves.",
      async () => { await hover(heading("Ownership plan"), 2500); await hover(heading("Responsibilities in scope"), 1500); await scrollToTop(); }],
  ]],
  ["Inside a case", [
    ["The tabs across the top hold the rest. ^Impact shows what the case touches: assets, connected sources, open risks and knowledge. Notice the warning at the top: GitHub could only be read partially, and Relay says so, instead of pretending the data is complete.",
      async () => { await caseTab(/^Impact/); await browse(2); }],
    ["^Knowledge lists everything to hand over. Each item can be marked handed over or noted as missing, and the whole pack downloads as Markdown.",
      async () => { await caseTab(/^Knowledge/); await hover(page.getByRole("link", { name: /handover pack/ }), 1500); }],
    ["^Tasks and readiness holds the work and the checks that must pass before the case can complete.",
      async () => { await caseTab(/^Tasks/); await hover(heading("Readiness"), 1500); }],
    ["^People lists participants and a privacy notice, so the people involved know what Relay reads about them.",
      async () => { await caseTab(/^People/); await hover(heading("Privacy and sharing"), 1500); }],
    ["^Approvals records each decision against a specific plan version, and Activity keeps the status history and comments.",
      async () => { await caseTab(/^Approvals/); await caseTab(/^Activity/); await hover(heading("Status history"), 1200); }],
  ]],
  ["Analysis and handover interview", [
    ["The ^Analysis tab groups findings into conflicts, missing evidence, work in flight and dependencies. It's marked Partial, because GitHub didn't sync cleanly, so gaps are treated as unknown, not absent.",
      async () => { await caseTab(/^Analysis/); await hover(heading(/^Conflicts/), 2000); }],
    ["Each finding is labelled, with its sources, and a manager can confirm or dismiss it. Suggested actions wait in the proposal tray on the right; nothing changes until a manager accepts one. Uncited claims are dropped, and evidence only managers may see never reaches a member.",
      async () => { await hover(heading(/^Missing evidence/), 1500); await hover(button("Confirm"), 1500); await browse(2); await scrollToTop(); }],
    ["The ^Interview tab turns those gaps into questions for the person leaving. They can answer, or say they don't know, it is not applicable, or they cannot share it. Reviewed answers can be promoted into knowledge, so tacit knowledge is captured before the person goes.",
      async () => { await caseTab(/^Interview/); await hover(button("Doesn't know"), 2000); await browse(2); await scrollToTop(); }],
  ]],
  ["Round 3 feature 3: AI Handover Copilot", [
    ["And now our third improvement, the AI Handover Copilot. Most handover documents are written in a hurry and trusted blindly; this one shows its evidence for every line. It lives in the ^Capsules tab: one brief for each recipient.",
      async () => { await caseTab(/^Capsules/); await click(page.getByRole("link", { name: /^For / }), 2000); }],
    ["Brief coverage at the top shows, for every responsibility in the case, whether the brief covers it with a cited source, mentions it without one, or misses it, critical items first, with a link to the interview to close the gaps.",
      () => hover(heading("Brief coverage"), 3000)],
    ["The rule is deliberately simple: a statement covers a responsibility when it names it, and counts as cited only when it rests on evidence that is still active."],
    ["The brief has fixed sections: what you now own, work in flight, knowledge gaps, risks and conflicts, recommended first steps, and where the work came from. Every statement is labelled, and I can expand its sources.",
      async () => { await hover(heading("What you now own"), 1500); await click(page.getByText(/^\d+ sources?: /).first(), 2000).catch(() => {}); await browse(3); }],
  ]],
  ["Copilot questions", [
    ["The recipient can ^ask questions. How should I deploy payments API?",
      () => ask("How should I deploy payments-api?")],
    ["While the copilot reads the evidence, a word on how we run AI in production. It holds no tools that can write anything. Every run is recorded on the AI agents page with its tokens and cost against the workspace's monthly budget, and if the model is unavailable, the rule-based brief still works.",
      () => ready()],
    ["And here is the answer: the steps come from the verified deploy procedure and the canary decision, with the sources listed right under it. It uses only the evidence behind this brief that I may see. Technically, every citation is validated by the server before it is shown.",
      () => hover(lastAnswer(), 2500)],
    ["Now something the evidence ^cannot answer: what is the AWS root password recovery process?",
      () => ask("What is the AWS root password recovery process?")],
    ["Now, the test that matters. A generic chatbot would happily write a plausible recovery procedure. For a handover, a confident wrong answer is worse than no answer at all.",
      () => ready()],
    ["And Relay answers: not in the evidence. It never invents an answer. If the AI is slow or fails, the page says so and offers a retry, and the rule-based brief is always usable.",
      () => hover(lastAnswer(), 2500)],
  ]],
  ["Versions, approval and acknowledgement", [
    ["Every edit creates a new version that needs approval again, so a reviewer approves exactly what the recipient will read. Compare shows the statements added and removed.",
      async () => {
        const versions = page.locator('[data-tour="capsule-versions"]');
        await hover(versions, 1500);
        const compare = versions.getByRole("link", { name: "Compare" });
        if (await compare.count()) {
          await click(compare.first(), 2000);
          await hover(heading(/^Changes from/), 2000);
          await click(link("Close comparison"), 1000);
        }
      }],
    ["The recipient acknowledges a specific approved version. After that, the brief shows their next steps: open tasks, the responsibilities they take over with a link to each history, and where to ask questions.",
      async () => {
        const ack = button("Acknowledge receipt");
        if (await ack.count()) await click(ack, 2000);
        await hover(page.getByText(/next steps/i).first(), 2000).catch(() => {});
      }],
  ]],
  ["Temporary coverage", [
    ["Not every change is permanent. Back in Cases, Priya on leave is a temporary coverage case.",
      async () => { await sidebar("Cases"); await click(link(/Priya on leave/), 1500); }],
    ["The plan shows Sara covering payments API operations and refund approvals from the start date, and Priya back in charge on her return. Coverage can be extended or ended early, and before Priya returns, Relay prepares a return briefing of what happened while she was away.",
      async () => { await hover(heading("Ownership plan"), 3000); await browse(2); await scrollToTop(); }],
  ]],
  ["A complete transfer, end to end", [
    ["Now, a complete transfer, end to end, live. In ^Cases, I click New case and choose a responsibility transfer.",
      async () => { await sidebar("Cases"); await click(link("New case"), 1200); await click(link(/Responsibility transfer/), 1200); }],
    ["I give it a ^title, and create it.",
      async () => {
        await type(page.getByLabel("Title"), "Access reviews move to Leo");
        await click(button("Create case"), 1200);
        await page.waitForURL(/\/cases\/[0-9a-f-]{36}$/);
        await settle();
      }],
    ["I add ^access reviews to the scope,",
      async () => {
        await click(page.getByLabel("Add responsibility"), 300);
        await page.getByLabel("Add responsibility").selectOption({ label: "Access reviews" });
        await click(button("Add"), 1200);
      }],
    ["choose ^Leo Martins as the recipient, and save the plan.",
      async () => {
        await click(page.getByLabel("Recipient", { exact: true }), 300);
        await page.getByLabel("Recipient", { exact: true }).selectOption({ label: "Leo Martins" });
        await click(button("Save"), 1200);
      }],
    ["I ^submit it for approval, and on the Approvals tab I approve this exact plan version.",
      async () => { await click(button("Submit for approval"), 1500); await caseTab(/^Approvals/); await click(button(/^Approve v\d+$/), 1500); }],
    ["Then, ^execute the handover. This ends the old assignment and starts the new one in a single audited transaction, and the ownership history is preserved, never overwritten.",
      () => click(button("Execute handover"), 2500)],
    ["Notifications and follow-up jobs go through a transactional outbox, written in the same database transaction as the change, so a crash can never lose a job or send it twice. And for critical work, the person who verifies completion must be someone who neither started nor approved the case."],
  ]],
  ["Follow-through: did the handover take hold?", [
    ["And this is where Relay goes beyond every tool we benchmarked: follow-through, on the case Overview tab. Approval and execution prove the plan was applied, but not that the handover worked.",
      async () => { await caseTab(/^Overview/); await hover(heading("Follow-through"), 2000); }],
    ["For each transferred responsibility Relay checks: is the new holder recorded, has the work been reviewed or shown activity since the handover, and are the handover tasks closed. Access reviews has just moved, so it shows Settling in.",
      () => hover(page.getByText("Settling in").first(), 2500)],
    ["The other states are Settled, Check in after fourteen quiet days, and New holder not recorded. It measures the work, not the person, so it never becomes employee surveillance. When we researched the catalogue, knowledge and offboarding tools out there, none of them closes this loop."],
  ]],
  ["Integrations", [
    ["Sidebar, ^Integrations: GitHub, Linear and Notion, all read-only. The GitHub App reads repository metadata, code owners and maintainers, never source code. And look: this sample's GitHub sync has failed with a 403, the app lost access to some repositories, and Relay shows exactly that.",
      async () => { await sidebar("Integrations"); await hover(heading("Repositories"), 2000); }],
    ["^Review suggestions is where code owners become ownership suggestions, which change nothing until a manager accepts them. None are open right now.",
      () => click(link("Review suggestions"), 2000)],
    ["^Linear brings projects and issues, and asks a person to link Linear users to directory people: here, A. Rao matches several people, so a human chooses.",
      async () => { await subnav("Integrations", "Linear"); await hover(heading("People to review"), 1500); }],
    ["^Notion imports only the pages you share, into Knowledge, unverified.",
      async () => { await subnav("Integrations", "Notion"); await hover(heading("Imported into Knowledge"), 1500); }],
    ["^Health shows each connector's state: GitHub's permission changed, Linear is stale, Notion is healthy. I can sync now or pause.",
      async () => { await subnav("Integrations", "Health"); await hover(button("Sync now"), 1500); }],
  ]],
  ["Automations and AI agents", [
    ["^Automations, in the sidebar, turn rules into notifications or follow-up tasks, on a schedule or on demand, and every run is recorded.",
      async () => { await sidebar("Automations"); await hover(button("Run now"), 2000); }],
    ["^AI agents lists every agent: impact analyst, knowledge interviewer, handover planner, readiness verifier, handover generator, handover copilot and memory narrator. Each shows its read-only tools and token budget, and recent runs show the model, tokens and time.",
      async () => { await sidebar("AI agents"); await hover(heading("Capabilities"), 1500); await hover(heading("Recent runs"), 1500); }],
    ["One switch turns AI off for the whole workspace, and everything else keeps working. Every AI run has an honest state, like a timed-out run in that list, so nothing spins forever, and AI never holds a tool that can write to your data.",
      () => hover(button("Switch off AI"), 2000)],
  ]],
  ["Audit, import, members and settings", [
    ["The admin pages are at the bottom of the sidebar. The ^audit log is append-only, written in the same transaction as each change. You can see the transfer I just made, and the outbox events behind it being processed.",
      () => sidebar("Audit log")],
    ["^Import brings people, responsibilities and ownership from a CSV file, with a preview before anything is written.",
      async () => { await sidebar("Import"); await hover(link("Download a template"), 1500); }],
    ["^Members invites people with a role: owner, admin, continuity manager, knowledge steward, team manager, member, auditor or guest. Permissions are enforced by the server, inside every service.",
      async () => { await sidebar("Members"); await hover(heading("Invite someone"), 1500); }],
    ["^Settings holds the continuity policies,",
      () => sidebar("Settings")],
    ["criticality ^tiers and responsibility types,",
      () => subnav("Settings", "Types & tiers")],
    ["the full ^permissions matrix for every role,",
      () => subnav("Settings", "Roles & access")],
    ["email ^preferences,",
      () => subnav("Settings", "Notifications")],
    ["and ^data controls: what Relay reads and why, full export, retention, ownership transfer, and workspace deletion, which needs the exact name typed to confirm.",
      async () => { await subnav("Settings", "Data & privacy"); await hover(heading("Delete workspace"), 1500); }],
  ]],
  ["Search anywhere", [
    ["From anywhere, Control K opens search: jump to a person or responsibility, or start a case without leaving the page.",
      async () => { await moveTo(800, 400); await page.keyboard.press("Control+K"); await pause(600); await page.keyboard.type("deploy", { delay: 80 }); await pause(1500); }],
    ["Results are grouped: responsibilities, assets, knowledge, risks and GitHub evidence. ^Enter jumps straight to the top one.",
      async () => { await page.keyboard.press("Enter"); await pause(2000); await settle(); }],
  ]],
  ["Why Relay", [
    ["So, why Relay? Today continuity lives in five tools and in people's heads, and it fails silently, on the day someone leaves. Relay brings it into one place and one lifecycle.",
      async () => { await sidebar("Overview"); await pause(1000); }],
    ["Memory Replay explains the past. The What If simulator shows the future and finds the right successor before anyone has left. The Handover Copilot writes a brief that proves every claim and admits what it does not know. And follow-through confirms the handover actually took hold.",
      () => hover(page.getByLabel("Continuity health"), 2000)],
    ["Under the hood, the database is the source of truth, AI only proposes cited drafts, and every workspace is isolated by Postgres row-level security, backed by nearly three hundred tests on a real database and twenty-three browser journeys. The judge guide in our repository maps every claim to its code and its tests."],
    ["When people move on, the work shouldn't stall. That's Relay. Thank you."],
  ]],
];

const beats = SCRIPT.flatMap(([chapter, lines], c) =>
  lines.map(([text, actions], b) => ({
    id: `${String(c + 1).padStart(2, "0")}-${String(b + 1).padStart(2, "0")}`,
    chapter,
    text,
    actions,
  })),
);

if (LIST) {
  console.log(JSON.stringify(beats.map(({ id, chapter, text }) => ({ id, chapter, text })), null, 1));
  process.exit(0);
}

// ---------------------------------------------------------------- recording
const require = createRequire(resolve("frontend/package.json"));
const { chromium } = require("@playwright/test");
const [outDir, timingFile] = process.argv.slice(2);
const timing = JSON.parse(readFileSync(timingFile, "utf8"));
mkdirSync(outDir, { recursive: true });
const LOG = join(outDir, "progress.log");
const log = (line) => appendFileSync(LOG, `${new Date().toISOString().slice(11, 19)} ${line}\n`);

// A visible cursor, click ripple and chapter caption.
const OVERLAY = `(() => {
  const css = document.createElement("style");
  css.textContent = \`
    #wt-cursor{position:fixed;z-index:2147483647;width:22px;height:22px;pointer-events:none;
      left:0;top:0;transform:translate(-3px,-2px);transition:left .05s linear,top .05s linear}
    .wt-ripple{position:fixed;z-index:2147483646;width:34px;height:34px;margin:-17px 0 0 -17px;
      border-radius:50%;border:3px solid rgba(15,118,110,.85);pointer-events:none;
      animation:wt-r .6s ease-out forwards}
    @keyframes wt-r{from{transform:scale(.3);opacity:1}to{transform:scale(1.6);opacity:0}}
    #wt-caption{position:fixed;z-index:2147483645;left:24px;bottom:22px;padding:8px 14px;
      border-radius:8px;background:rgba(17,24,39,.86);color:#fff;font:600 15px/1.3 system-ui;
      pointer-events:none;letter-spacing:.01em}
    nextjs-portal{display:none!important}\`;
  // sessionStorage throws on about:blank, so every access is guarded.
  const load = (key, fallback) => { try { return sessionStorage.getItem(key) || fallback; } catch { return fallback; } };
  const save = (key, value) => { try { sessionStorage.setItem(key, value); } catch {} };
  const mount = () => {
    if (!document.body || !document.head || document.getElementById("wt-cursor")) return;
    if (!css.isConnected) document.head.appendChild(css);
    const c = document.createElement("div");
    c.id = "wt-cursor";
    c.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M3 2l7 19 2.6-7.6L20 11z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    const p = JSON.parse(load("wt-pos", "[800,450]"));
    c.style.left = p[0] + "px"; c.style.top = p[1] + "px";
    document.body.appendChild(c);
    const cap = document.createElement("div");
    cap.id = "wt-caption";
    cap.textContent = load("wt-chapter", "");
    if (!cap.textContent) cap.style.display = "none";
    document.body.appendChild(cap);
  };
  document.addEventListener("mousemove", (e) => {
    const c = document.getElementById("wt-cursor");
    if (c) { c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px"; }
    save("wt-pos", JSON.stringify([e.clientX, e.clientY]));
  }, true);
  document.addEventListener("mousedown", (e) => {
    const r = document.createElement("div");
    r.className = "wt-ripple"; r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px";
    document.body.appendChild(r); setTimeout(() => r.remove(), 650);
  }, true);
  // Hydration can drop foreign nodes from <body>; put them back if that happens.
  document.addEventListener("DOMContentLoaded", mount);
  setInterval(mount, 400);
  // A one-pixel heartbeat repaint keeps screencast frames flowing through still moments.
  const beat = document.createElement("div");
  beat.style.cssText = "position:fixed;right:0;bottom:0;width:1px;height:1px;pointer-events:none;z-index:2147483647";
  setInterval(() => {
    if (!beat.isConnected && document.body) document.body.appendChild(beat);
    beat.style.opacity = beat.style.opacity === "0.01" ? "0.02" : "0.01";
  }, 200);
})();`;

// The browser renders off-screen and streams its own frames (CDP screencast) into ffmpeg,
// so the take does not depend on what is on the desktop. 1536x864 at 1.25x is 1920x1080.
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1536, height: 864 },
  deviceScaleFactor: 1.25,
  storageState: "frontend/e2e/.auth/user.json",
});
await context.addInitScript(OVERLAY);
page = await context.newPage();
log("browser open");
await page.goto(BASE + "/");
await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => {});
await page.waitForTimeout(1500);
page.on("dialog", (d) => d.accept());
page.setDefaultTimeout(10_000);
page.setDefaultNavigationTimeout(30_000);

// Frames arrive only when the page changes; wall-clock timestamps let ffmpeg hold each
// frame until the next one, and the output is resampled to a constant 25 fps.
const screen = spawn(
  "ffmpeg",
  ["-y", "-f", "image2pipe", "-c:v", "mjpeg", "-use_wallclock_as_timestamps", "1", "-i", "-",
    "-vf", "scale=1920:1080:flags=lanczos", "-fps_mode", "cfr", "-r", "25",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
    join(outDir, "walkthrough.mkv")],
  { stdio: ["pipe", "ignore", "ignore"] },
);
const cdp = await context.newCDPSession(page);
let firstFrame;
const started = new Promise((done) => (firstFrame = done));
cdp.on("Page.screencastFrame", ({ data, sessionId }) => {
  screen.stdin.write(Buffer.from(data, "base64"));
  firstFrame();
  cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
});
await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
await started;
const t0 = Date.now();
log("screen recording started");

const GAP = 350; // a breath between sentences
const REACH = 700; // how long the pointer takes to reach what a cue word names
const marks = [];
let caption = "";
for (const beat of beats) {
  if (beat.chapter !== caption) {
    caption = beat.chapter;
    await page.evaluate((text) => {
      try { sessionStorage.setItem("wt-chapter", text); } catch {}
      const cap = document.getElementById("wt-caption");
      if (cap) { cap.textContent = text; cap.style.display = ""; }
    }, caption).catch(() => {});
  }
  const start = Date.now();
  marks.push({ id: beat.id, at: (start - t0) / 1000 });
  const { dur = 3, cues = [] } = timing[beat.id] ?? {};
  const speech = dur * 1000;
  // Start moving a little before the cue word, so the pointer arrives as it is spoken.
  const cue = async (n) => {
    const left = start + (cues[n] ?? 0) * 1000 - REACH - Date.now();
    if (left > 0) await pause(left);
  };
  if (beat.actions) {
    try {
      if (cues.length) await cue(0);
      await Promise.race([
        beat.actions(cue),
        new Promise((_, reject) => setTimeout(() => reject(new Error("beat time limit")), speech + 120_000)),
      ]);
    } catch (e) {
      log(`[${beat.id}] failed: ${String(e.message).split("\n")[0]}`);
    }
  }
  const left = speech + GAP - (Date.now() - start);
  if (left > 0) await pause(left);
  log(`[${beat.id}] ${((Date.now() - start) / 1000).toFixed(1)}s (speech ${(speech / 1000).toFixed(1)}s)`);
}

await pause(2000);
writeFileSync(join(outDir, "marks.json"), JSON.stringify(marks, null, 1));
// Close ffmpeg's input so the file is finalised, then close the browser.
await cdp.send("Page.stopScreencast").catch(() => {});
const stopped = new Promise((done) => screen.on("exit", done));
screen.stdin.end();
await stopped;
await context.close();
await browser.close();
log("finished");
console.log(`done in ${((Date.now() - t0) / 60000).toFixed(1)} min`);
