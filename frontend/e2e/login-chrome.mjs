// `pnpm e2e:login`: opens ordinary Google Chrome (not automation-controlled, so sign-in
// bot checks behave normally) with a throwaway profile in the OS temp folder. Sign in yourself;
// once Relay loads, Playwright attaches over the local DevTools port, saves the session to
// e2e/.auth/user.json and closes Chrome. Credentials are never typed or stored by this script.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { chromium } from "@playwright/test";

const BASE = process.env.RELAY_E2E_BASE_URL ?? "http://localhost:3000";
const PORT = 9333;
const CHROME =
  process.env.CHROME_PATH ??
  [
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
  ].find(existsSync);
if (!CHROME) throw new Error("Google Chrome not found; set CHROME_PATH.");

// Outside the repo, so formatters and linters never scan a browser profile.
const profile = join(tmpdir(), "relay-e2e-chrome");
mkdirSync(profile, { recursive: true });
const chrome = spawn(
  CHROME,
  [
    `--remote-debugging-port=${PORT}`,
    "--remote-debugging-address=127.0.0.1",
    `--user-data-dir=${profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    `${BASE}/sign-in`,
  ],
  { stdio: "ignore" },
);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const deadline = Date.now() + 10 * 60_000;
let browser;
while (!browser && Date.now() < deadline) {
  await sleep(1000);
  browser = await chromium.connectOverCDP(`http://127.0.0.1:${PORT}`).catch(() => undefined);
}
if (!browser) throw new Error("Could not reach Chrome's DevTools port.");

console.log("Chrome is open. Sign in to Relay there; waiting up to 10 minutes…");
const signedIn = new RegExp(`^${BASE.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/(workspaces|w/)`);
const context = browser.contexts()[0];
while (Date.now() < deadline) {
  if (context.pages().some((p) => signedIn.test(p.url()))) {
    await sleep(1500); // let the session cookie settle
    await context.storageState({ path: "e2e/.auth/user.json" });
    console.log("Session saved to e2e/.auth/user.json.");
    await browser.close();
    chrome.kill();
    process.exit(0);
  }
  await sleep(1000);
}
chrome.kill();
throw new Error("Timed out waiting for sign-in.");
