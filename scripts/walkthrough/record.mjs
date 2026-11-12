// Records the judges' walkthrough as one continuous take: starts at the landing page and
// only clicks what a person can see. Each chapter waits for at least the length of its
// narration clip, and the start time of every chapter is written out for the voiceover.
//
// Usage (from the repo root, app running locally, signed-in session saved by the e2e setup):
//   node scripts/walkthrough/record.mjs <outDir> <durations.json>
import { spawn } from "node:child_process";
import { appendFileSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";

const require = createRequire(resolve("frontend/package.json"));
const { chromium } = require("@playwright/test");

const [outDir, durationsFile] = process.argv.slice(2);
const BASE = process.env.RELAY_BASE_URL ?? "http://localhost:3000";
const narration = JSON.parse(readFileSync("scripts/walkthrough/narration.json", "utf8"));
const durations = JSON.parse(readFileSync(durationsFile, "utf8"));
const SIZE = { width: 1600, height: 900 };
mkdirSync(outDir, { recursive: true });
const LOG = join(outDir, "progress.log");
const log = (line) => appendFileSync(LOG, `${new Date().toISOString().slice(11, 19)} ${line}\n`);

// A visible cursor, click ripple and chapter caption (headless video has no OS cursor).
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
      pointer-events:none;letter-spacing:.01em}\`;
  const mount = () => {
    if (!document.body || document.getElementById("wt-cursor")) return;
    document.head.appendChild(css);
    const c = document.createElement("div");
    c.id = "wt-cursor";
    c.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M3 2l7 19 2.6-7.6L20 11z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    const p = JSON.parse(sessionStorage.getItem("wt-pos") || "[800,450]");
    c.style.left = p[0] + "px"; c.style.top = p[1] + "px";
    document.body.appendChild(c);
    const cap = document.createElement("div");
    cap.id = "wt-caption";
    cap.textContent = sessionStorage.getItem("wt-chapter") || "";
    if (!cap.textContent) cap.style.display = "none";
    document.body.appendChild(cap);
  };
  document.addEventListener("mousemove", (e) => {
    const c = document.getElementById("wt-cursor");
    if (c) { c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px"; }
    sessionStorage.setItem("wt-pos", JSON.stringify([e.clientX, e.clientY]));
  }, true);
  document.addEventListener("mousedown", (e) => {
    const r = document.createElement("div");
    r.className = "wt-ripple"; r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px";
    document.body.appendChild(r); setTimeout(() => r.remove(), 650);
  }, true);
  new MutationObserver(mount).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", mount);
  mount();
})();`;

// A real, full-screen browser window, recorded from the screen by ffmpeg (gdigrab).
const browser = await chromium.launch({ headless: false, args: ["--window-position=0,0", "--start-fullscreen"] });
const context = await browser.newContext({
  viewport: null,
  storageState: "frontend/e2e/.auth/user.json",
});
await context.addInitScript(OVERLAY);
const page = await context.newPage();
log("browser open");
await page.goto(BASE + "/");
await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => {});
await page.waitForTimeout(1500);
const screen = spawn(
  "ffmpeg",
  ["-y", "-f", "gdigrab", "-framerate", "25", "-draw_mouse", "0",
    "-offset_x", "0", "-offset_y", "0", "-video_size", "1920x1080", "-i", "desktop",
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p",
    join(outDir, "walkthrough.mkv")],
  { stdio: ["pipe", "ignore", "ignore"] },
);
const t0 = Date.now();
log("screen recording started");
page.on("dialog", (d) => d.accept());
page.setDefaultTimeout(10_000);
page.setDefaultNavigationTimeout(30_000);

let cursor = { x: 800, y: 450 };
const pause = (ms) => page.waitForTimeout(ms);
const settle = () => page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => {});
const visible = (loc) => loc.filter({ visible: true }).first();

async function moveTo(x, y) {
  const steps = Math.max(12, Math.round(Math.hypot(x - cursor.x, y - cursor.y) / 18));
  await page.mouse.move(x, y, { steps });
  cursor = { x, y };
}
async function point(loc) {
  const el = visible(loc);
  await el.scrollIntoViewIfNeeded();
  await pause(250);
  const box = await el.boundingBox();
  if (!box) throw new Error("no box");
  await moveTo(box.x + Math.min(box.width / 2, 120), box.y + box.height / 2);
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
async function scroll(pixels, stepMs = 30) {
  const step = pixels > 0 ? 60 : -60;
  for (let done = 0; Math.abs(done) < Math.abs(pixels); done += step) {
    await page.mouse.wheel(0, step);
    await pause(stepMs);
  }
  await pause(500);
}
async function scrollToTop() {
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await page.locator("main").first().evaluate((m) => m.scrollTo?.({ top: 0, behavior: "smooth" }));
  await pause(900);
}
const sidebar = (label) =>
  click(page.getByRole("navigation", { name: "Workspace" }).getByRole("link", { name: label, exact: true }));
const link = (name) => page.getByRole("link", { name });
const button = (name) => page.getByRole("button", { name });

const marks = [];
async function chapter(id, actions) {
  const seg = narration.find((n) => n.id === id);
  const start = Date.now();
  marks.push({ id, at: (start - t0) / 1000 });
  await page.evaluate((text) => {
    sessionStorage.setItem("wt-chapter", text);
    const cap = document.getElementById("wt-caption");
    if (cap) { cap.textContent = text; cap.style.display = ""; }
  }, seg.chapter).catch(() => {});
  log(`[${id}] start`);
  // A chapter may not hang the take: give up on it after its narration plus two minutes.
  const limit = (durations[id] ?? 30) * 1000 + 120_000;
  try {
    await Promise.race([
      actions(),
      new Promise((_, reject) => setTimeout(() => reject(new Error("chapter time limit")), limit)),
    ]);
  } catch (e) {
    log(`[${id}] step failed: ${String(e.message).split("\n")[0]}`);
  }
  const minimum = (durations[id] ?? 0) * 1000 + 1200;
  const left = minimum - (Date.now() - start);
  if (left > 0) await pause(left);
  log(`[${id}] done ${((Date.now() - start) / 1000).toFixed(1)}s`);
}

// ---------------------------------------------------------------- the walkthrough
const caseTab = (name) =>
  click(page.getByRole("navigation", { name: "Case sections" }).getByRole("link", { name }), 2500);
const subnav = (nav, name) =>
  click(page.getByRole("navigation", { name: nav }).getByRole("link", { name, exact: true }), 2500);
const heading = (name) => page.getByRole("heading", { name });
const browse = async (n = 4, px = 300) => {
  for (let i = 0; i < n; i++) await scroll(px, 50);
};


await chapter("intro", async () => {
  await pause(3000);
  await hover(page.getByRole("heading", { level: 1 }), 5000);
  await scroll(250, 60);
  await pause(4000);
  await scrollToTop();
});

await chapter("landing", async () => {
  for (let i = 0; i < 3; i++) await scroll(260, 40);
  for (const step of ["Evidence, not guesses", "People decide", "A handover that fits", "Ownership moves"]) {
    await click(button(step), 2500);
  }
  await browse(8, 320);
  await scrollToTop();
});

await chapter("workspaces", async () => {
  await click(link("Go to your workspaces →"), 1500);
  await page.waitForURL(/\/workspaces$/);
  await hover(button("Create sample workspace"), 2000);
  await click(button("Create sample workspace"), 500);
  const limited = page.getByRole("alert").filter({ hasText: /several sample workspaces/ });
  await Promise.race([
    page.waitForURL(/\/w\/[0-9a-f-]{36}$/, { timeout: 90_000 }).catch(() => {}),
    limited.waitFor({ timeout: 90_000 }).catch(() => {}),
  ]);
  if (await limited.isVisible()) {
    await click(page.getByRole("link", { name: /Northwind Labs \(demo\)/ }).last(), 1000);
    await page.waitForURL(/\/w\/[0-9a-f-]{36}$/);
  }
  await settle();
});

await chapter("overview", async () => {
  await pause(1500);
  const start = page.getByRole("region", { name: "Getting started" });
  if (await start.isVisible()) await hover(start, 3000);
  await hover(page.getByLabel("Continuity health"), 3500);
  await browse(4);
  await pause(1500);
  await browse(4);
  await scrollToTop();
});

await chapter("learn", async () => {
  await sidebar("Learn Relay");
  await hover(page.getByRole("switch", { name: "Product guidance" }), 2500);
  await click(button("Restart tutorial progress"), 1500);
  const basics = page.getByRole("listitem").filter({ hasText: "Find your way around" });
  await click(basics.getByRole("link", { name: /Start|Resume|Replay/ }), 2500);
  const dialog = page.getByRole("dialog");
  for (let i = 0; i < 3; i++) await click(dialog.getByRole("button", { name: "Next" }), 3500);
  await click(dialog.getByRole("button", { name: "Back" }), 2500);
  await click(dialog.getByRole("button", { name: "Next" }), 2500);
  await click(dialog.getByRole("button", { name: "Done" }), 1500);
});

await chapter("mywork", async () => {
  await sidebar("My Work");
  await hover(heading("Knowledge to review"), 3000);
  await hover(heading("Cases I coordinate"), 3000);
  await sidebar("Inbox");
  await pause(3000);
});

await chapter("people", async () => {
  await sidebar("People & Teams");
  await hover(heading("Departments"), 2000);
  await hover(heading("People"), 2000);
  await hover(heading("Teams"), 2000);
  await click(page.getByRole("link", { name: "Arjun Rao", exact: true }), 2000);
  await hover(heading("Ownership roles"), 2500);
  await hover(heading("Open risks"), 2000);
  await hover(heading("Active continuity cases"), 2000);
  await hover(link("What if Arjun is unavailable?"), 1500);
  await sidebar("People & Teams");
  await click(page.locator('main a[href*="/teams/"]'), 2500);
  await sidebar("People & Teams");
  await click(page.locator('main a[href*="/departments/"]'), 2500);
  await hover(page.getByRole("link", { name: /Continuity Debt/ }), 2000);
});

await chapter("responsibilities", async () => {
  await sidebar("Responsibilities");
  await pause(1500);
  await hover(page.locator('[data-tour="responsibility-table"]'), 3000);
  await click(page.getByRole("link", { name: "Production deployments", exact: true }), 1500);
  for (const h of ["Stewardship", "Current owners", "Continuity", "Dependencies", "Knowledge", "Assets", "Ownership history"]) {
    await hover(heading(h), 2200);
  }
  await scrollToTop();
});

await chapter("knowledge", async () => {
  await sidebar("Knowledge");
  await hover(button("Still accurate"), 2500);
  await click(page.getByRole("link", { name: "Deploy payments-api", exact: true }), 2500);
  await hover(heading("Possible conflicts"), 3500);
  await hover(heading("Versions"), 3000);
});

await chapter("assets", async () => {
  await sidebar("Assets");
  await hover(page.getByRole("link", { name: "Legacy SFTP bridge" }), 3000);
  await click(page.getByRole("link", { name: "billing-db", exact: true }), 2500);
  for (const h of ["Details", "Linked work and knowledge", "Looked after by", "Risks through its stewards"]) {
    await hover(heading(h), 2200);
  }
});

await chapter("replay", async () => {
  await sidebar("Responsibilities");
  await click(page.getByRole("link", { name: "Production deployments", exact: true }), 1500);
  await click(link("Memory replay"), 1500);
  await page.waitForURL(/\/timeline$/);
  await settle();
  const filters = page.getByRole("group", { name: "Filter by category" });
  await click(filters.getByRole("button", { name: /Incident/ }), 3500);
  await click(filters.getByRole("button", { name: /^All/ }), 2000);
  await click(button("Replay history"), 7000);
  await click(button("Pause"), 1500);
  await click(button("Inspect"), 3500);
});

await chapter("replay_ai", async () => {
  const explain = page.getByRole("button", { name: "Explain this history" });
  if (await explain.isVisible()) await click(explain, 500);
  await page
    .getByText(/Inferred ·|AI is not configured|switched off|could not answer/)
    .first()
    .waitFor({ timeout: 90_000 });
  await hover(page.getByText(/Inferred ·/).first(), 3000).catch(() => {});
  await type(page.getByLabel("Your question"), "Why does every payments-api deploy need a canary?");
  await click(button("Ask"), 500);
  const answer = page.getByText(/From the history|Search results, not an answer|Not in the history/).last();
  await answer.waitFor({ timeout: 90_000 });
  await point(answer);
  await pause(4000);
});

await chapter("risks", async () => {
  await sidebar("Risks");
  await pause(1500);
  await browse(2);
  await scrollToTop();
  await click(page.locator('main a[href*="/risks/"]'), 2500);
  await hover(heading("Why this is a risk"), 3000);
  await hover(heading("Recommended action"), 3000);
});

await chapter("insights", async () => {
  await sidebar("Insights");
  await pause(1500);
  await hover(heading("Continuity Debt"), 3000);
  await hover(heading("Key-person exposure"), 4000);
  await hover(link("What if Arjun is away?"), 2500);
  for (const h of ["Coverage", "Knowledge health", "Continuity operations"]) await hover(heading(h), 2000);
  await scrollToTop();
  await click(link(/Trends/), 3000);
  await hover(heading("Saved snapshots"), 2500);
  await sidebar("Insights");
  await hover(heading("Key-person exposure"), 1500);
});

await chapter("whatif", async () => {
  await click(link("What if Arjun is away?"), 1500);
  await click(page.getByLabel("is unavailable for"), 400);
  await page.getByLabel("is unavailable for").selectOption({ label: "2 weeks" });
  await pause(800);
  await click(button("Run simulation"), 2500);
  await hover(page.getByText("Nobody", { exact: true }), 2500);
  await click(page.getByText("Why it is affected"), 3000);
  await hover(page.getByText("Due while away"), 2000);
});

await chapter("candidates", async () => {
  await hover(heading("Who could cover?"), 3000);
  await scroll(300, 50);
  await click(link("Simulate with Dev"), 2500);
  await hover(page.getByText("Simulation only. Nothing in the workspace was changed."), 3500);
  await click(link("Plan a real handover"), 3000);
  await hover(page.getByLabel("Title"), 2500);
});

await chapter("case", async () => {
  await sidebar("Cases");
  await click(link(/Arjun Rao is leaving Platform/), 2000);
  await hover(heading("Blockers"), 3000);
  await hover(heading("Ownership plan"), 4000);
  await hover(heading("Responsibilities in scope"), 2500);
  await scrollToTop();
});

await chapter("case_tabs", async () => {
  await caseTab(/^Impact/);
  await browse(2);
  await caseTab(/^Knowledge/);
  await hover(page.getByRole("link", { name: /handover pack/ }), 2500);
  await caseTab(/^Tasks/);
  await hover(heading("Readiness"), 2500);
  await caseTab(/^People/);
  await hover(heading("Privacy and sharing"), 2500);
  await caseTab(/^Approvals/);
  await caseTab(/^Activity/);
  await hover(heading("Status history"), 2000);
});

await chapter("case_ai", async () => {
  await click(link(/^Analysis/), 2500);
  await hover(heading(/^Conflicts/), 3000);
  await hover(heading(/^Missing evidence/), 2500);
  await hover(button("Confirm"), 2000);
  await browse(3);
  await scrollToTop();
  await click(link(/^Interview/), 2500);
  await hover(button("Doesn't know"), 2500);
  await browse(2);
  await scrollToTop();
});

await chapter("brief", async () => {
  await click(link(/^Capsules/), 2000);
  await click(page.getByRole("link", { name: /^For / }), 2500);
  await hover(heading("Brief coverage"), 4000);
  await hover(heading("What you now own"), 3000);
  await click(page.getByText(/^\d+ sources?: /).first(), 2500).catch(() => {});
  await browse(4);
});

await chapter("copilot", async () => {
  const copilot = page.getByRole("region", { name: "Ask about this handover" });
  const answers = copilot.getByRole("article");
  for (const q of ["How should I deploy payments-api?", "What is the AWS root password recovery process?"]) {
    const before = await answers.count();
    await type(copilot.getByLabel("Your question"), q);
    await click(copilot.getByRole("button", { name: "Ask" }), 500);
    await answers.nth(before).waitFor({ timeout: 90_000 });
    await page
      .waitForFunction(
        ([n]) => {
          const all = document.querySelectorAll('section[aria-labelledby="copilot-heading"] article');
          return /Answer from the evidence|Not in the evidence|Search results/.test(all[n]?.textContent ?? "");
        },
        [before],
        { timeout: 90_000 },
      )
      .catch(() => {});
    await point(answers.nth(before));
    await pause(3500);
  }
});

await chapter("versions", async () => {
  const versions = page.locator('[data-tour="capsule-versions"]');
  await hover(versions, 2000);
  const compare = versions.getByRole("link", { name: "Compare" });
  if (await compare.count()) {
    await click(compare.first(), 3000);
    await hover(heading(/^Changes from/), 3000);
    await click(link("Close comparison"), 1500);
  }
  const ack = button("Acknowledge receipt");
  if (await ack.count()) await click(ack, 3000);
  await hover(page.getByText(/next steps/i).first(), 3000).catch(() => {});
});

await chapter("coverage", async () => {
  await sidebar("Cases");
  await click(link(/Priya on leave/), 2000);
  await hover(heading("Ownership plan"), 5000);
  await browse(2);
  await scrollToTop();
});

await chapter("transfer", async () => {
  await sidebar("Cases");
  await click(link("New case"), 1500);
  await click(link(/Responsibility transfer/), 1500);
  await type(page.getByLabel("Title"), "Access reviews move to Leo");
  await click(button("Create case"), 1500);
  await page.waitForURL(/\/cases\/[0-9a-f-]{36}$/);
  await settle();
  await click(page.getByLabel("Add responsibility"), 300);
  await page.getByLabel("Add responsibility").selectOption({ label: "Access reviews" });
  await click(button("Add"), 1500);
  await click(page.getByLabel("Recipient", { exact: true }), 300);
  await page.getByLabel("Recipient", { exact: true }).selectOption({ label: "Leo Martins" });
  await click(button("Save"), 1500);
  await click(button("Submit for approval"), 2000);
  await caseTab(/^Approvals/);
  await click(button(/^Approve v\d+$/), 2000);
  await click(button("Execute handover"), 2500);
});

await chapter("follow", async () => {
  await caseTab(/^Overview/);
  await hover(heading("Follow-through"), 4000);
  await hover(page.getByText("Settling in").first(), 3000);
  await hover(heading("Ownership plan"), 2000);
});

await chapter("integrations", async () => {
  await sidebar("Integrations");
  await hover(heading("Repositories"), 2500);
  await click(link("Review suggestions"), 2500);
  await subnav("Integrations", "Linear");
  await hover(heading("People to review"), 2500);
  await subnav("Integrations", "Notion");
  await hover(heading("Imported into Knowledge"), 2500);
  await subnav("Integrations", "Health");
  await hover(button("Sync now"), 2000);
});

await chapter("agents", async () => {
  await sidebar("Automations");
  await hover(button("Run now"), 3000);
  await sidebar("AI agents");
  await hover(heading("Capabilities"), 3000);
  await hover(heading("Recent runs"), 3000);
  await hover(button("Switch off AI"), 2000);
});

await chapter("admin", async () => {
  await sidebar("Audit log");
  await pause(3000);
  await sidebar("Import");
  await hover(link("Download a template"), 2500);
  await sidebar("Members");
  await hover(heading("Invite someone"), 2500);
  await sidebar("Settings");
  await pause(2000);
  for (const tab of ["Types & tiers", "Roles & access", "Notifications", "Data & privacy"]) {
    await subnav("Settings", tab);
  }
  await hover(heading("Delete workspace"), 2000);
});

await chapter("search", async () => {
  await moveTo(800, 400);
  await page.keyboard.press("Control+K");
  await pause(800);
  await page.keyboard.type("deploy", { delay: 80 });
  await pause(2500);
  await page.keyboard.press("Enter");
  await pause(3000);
});

await chapter("close", async () => {
  await sidebar("Overview");
  await pause(2000);
  await hover(page.getByLabel("Continuity health"), 5000);
});

await pause(1500);
writeFileSync(join(outDir, "marks.json"), JSON.stringify(marks, null, 1));
// Stop the screen recording cleanly ("q"), so the file is finalised, then close the browser.
const stopped = new Promise((done) => screen.on("exit", done));
screen.stdin.write("q");
await stopped;
await context.close();
await browser.close();
log("finished");
writeFileSync(join(outDir, "marks.json"), JSON.stringify(marks, null, 1));
console.log(`done in ${((Date.now() - t0) / 60000).toFixed(1)} min`);
