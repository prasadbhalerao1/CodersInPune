// Records the judges' walkthrough as one continuous take: starts at the landing page and
// only clicks what a person can see. The script is a list of beats; each beat is one or two
// sentences of narration plus the actions they describe. A beat starts its actions as its
// sentence starts, and the next beat waits until the sentence has finished, so the voice
// always describes what is on screen. Every beat's start time is written out for the mix.
//
// Usage (from the repo root; signs in through the landing page of RELAY_BASE_URL, the live site by default):
//   node scripts/walkthrough/record.mjs --list > scripts/walkthrough/narration.json
//   python scripts/walkthrough/voice.py scripts/walkthrough/narration.json <voiceDir>
//   node scripts/walkthrough/record.mjs <outDir> <voiceDir>/timing.json
// A ^ in a sentence marks a cue word: the beat's actions start just before it is spoken,
// so the click lands on the word; an action can wait for later cues with cue(n).
import { spawn } from "node:child_process";
import { appendFileSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";

const BASE = process.env.RELAY_BASE_URL ?? "https://midnight-ciphers.cv";
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
  // The wheel scrolls whatever is under the pointer: leave the sidebar for the page first.
  if (cursor.x < 320) await moveTo(700 + Math.random() * 260, 430 + Math.random() * 120);
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
import { pathToFileURL } from "node:url";
// WALK_SCRIPT records another script with the same helpers (e.g. a pickup shot to splice in).
const { default: build } = await import(
  process.env.WALK_SCRIPT ? pathToFileURL(resolve(process.env.WALK_SCRIPT)).href : "./script.mjs"
);
const helpers = () => ({
  page, pause, settle, click, type, hover, scroll, scrollToTop, browse, link, button,
  heading, sidebar, caseTab, subnav, background, ready, copilot, ask,
});
let SCRIPT = build(helpers());

const toBeats = () => SCRIPT.flatMap(([chapter, lines], c) =>
  lines.map(([text, actions], b) => ({
    id: `${String(c + 1).padStart(2, "0")}-${String(b + 1).padStart(2, "0")}`,
    chapter,
    text,
    actions,
  })),
);
let beats = toBeats();

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
});
await context.addInitScript(OVERLAY);
page = await context.newPage();
SCRIPT = build(helpers());
beats = toBeats();
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
