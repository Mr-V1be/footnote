// Shared by the screenshot sets: demo sign-in and the capture loop that
// shoots every screen in three viewports and both themes with headless
// Chromium (sound muted) and reports horizontal overflow and page errors.
import { execFile } from "node:child_process";
import { mkdir, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { chromium } from "playwright";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
export const BASE = process.env.WEB_URL ?? "http://localhost:46300";
export const VIEWPORTS = {
  // The smallest phone the layout is checked on; only for screens that ask for it.
  small: { width: 360, height: 780 },
  phone: { width: 390, height: 844 },
  tablet: { width: 768, height: 1024 },
  desktop: { width: 1280, height: 800 },
};
const DEFAULT_VIEWPORTS = ["phone", "tablet", "desktop"];
// Appended to file names, e.g. SUFFIX=before for the "before" half of a pair.
const SUFFIX = process.env.SUFFIX ? `-${process.env.SUFFIX}` : "";
const THEMES = ["light", "dark"];
const SETTLE_MS = 700;

/** Demo passwords by email, read from the project's seed file. */
export async function credentials() {
  const seed = await readFile(resolve(ROOT, "backend/demo/seed.yaml"), "utf8");
  const pairs = new Map();
  for (const match of seed.matchAll(
    /email: (\S+)\n\s+first_name: .*\n\s+last_name: .*\n\s+password: (\S+)/g,
  )) {
    pairs.set(match[1], match[2]);
  }
  return pairs;
}

/**
 * Returns the demo stand to its seed after a run that changed it (uploads,
 * questions, corrections, a spent plan, test webhooks) and waits until its
 * documents are checked again; model answers come from the cache, so this
 * costs no model requests. KEEP_STAND=1 leaves the stand as the run left it
 * (make demo-refresh restores it once, at the end).
 */
export async function restoreStand() {
  if (process.env.KEEP_STAND === "1") return;
  const run = promisify(execFile);
  const backend = { cwd: resolve(ROOT, "backend"), maxBuffer: 16 * 1024 * 1024 };
  await run("uv", ["run", "--frozen", "snoska", "demo", "reset"], backend);
  await run("uv", ["run", "--frozen", "snoska", "checks", "wait"], backend);
  console.log("demo stand restored to its seed");
}

export async function signIn(browser, email, password) {
  const context = await browser.newContext({ viewport: VIEWPORTS.desktop });
  const page = await context.newPage();
  // The root is the public landing now; sign-in is its own route.
  await page.goto(`${BASE}/auth/login`);
  await page.fill("#username", email);
  if (!(await page.locator("#password").isVisible())) {
    await page.click("#kc-login");
    await page.waitForSelector("#password");
  }
  await page.fill("#password", password);
  await page.click("#kc-login");
  await page.waitForURL((url) => url.href.startsWith(BASE) && !url.pathname.startsWith("/auth"), {
    timeout: 60_000,
  });
  const state = await context.storageState();
  await context.close();
  return state;
}

/**
 * SCREENS selects by parts of names, comma-separated; "!" before a part
 * leaves those screens out: SCREENS=result,!queued
 */
function wanted(name, filter) {
  const terms = (filter ?? "").split(",").filter(Boolean);
  const excluded = terms.filter((term) => term.startsWith("!")).map((term) => term.slice(1));
  const included = terms.filter((term) => !term.startsWith("!"));
  if (excluded.some((term) => name.includes(term))) return false;
  return included.length === 0 || included.some((term) => name.includes(term));
}

/**
 * Captures each screen into `outDir`. A screen is `{ name, user, run, after?, viewports? }`:
 * `run(page, { viewport, theme })` prepares the page, the runner shoots it, and
 * `after` undoes what the screen changed. A screen without a user is captured
 * signed out.
 */
export async function capture({ screens, users, outDir }) {
  const out = resolve(ROOT, outDir);
  await mkdir(out, { recursive: true });
  const selected = screens.filter((screen) => wanted(screen.name, process.env.SCREENS));
  const passwords = await credentials();
  const browser = await chromium.launch({ args: ["--mute-audio"] });
  const states = {};
  for (const user of new Set(selected.map((screen) => screen.user).filter(Boolean))) {
    states[user] = await signIn(browser, users[user], passwords.get(users[user]));
  }
  const problems = [];
  for (const screen of selected) {
    for (const [viewport, size] of Object.entries(VIEWPORTS)) {
      if (!(screen.viewports ?? DEFAULT_VIEWPORTS).includes(viewport)) continue;
      for (const theme of THEMES) {
        const context = await browser.newContext({
          viewport: size,
          deviceScaleFactor: 1,
          colorScheme: theme,
          storageState: screen.user ? states[screen.user] : undefined,
          isMobile: viewport === "phone" || viewport === "small",
          hasTouch: viewport !== "desktop",
        });
        await context.addCookies([{ name: "snoska_theme", value: theme, url: BASE }]);
        const page = await context.newPage();
        page.on("pageerror", (error) =>
          problems.push(`${screen.name} ${viewport} ${theme}: ${error.message}`),
        );
        try {
          await screen.run(page, { viewport, theme });
          await page.waitForTimeout(SETTLE_MS);
          const overflow = await page.evaluate(
            () => document.documentElement.scrollWidth - window.innerWidth,
          );
          if (overflow > 0)
            problems.push(`${screen.name} ${viewport} ${theme}: horizontal overflow ${overflow}px`);
          await page.screenshot({
            path: `${out}/${screen.name}--${viewport}-${theme}${SUFFIX}.png`,
          });
          if (screen.after) await screen.after(page, { viewport, theme });
        } catch (error) {
          problems.push(`${screen.name} ${viewport} ${theme}: ${error.message.split("\n")[0]}`);
        }
        await context.close();
      }
    }
    console.log(`captured ${screen.name}`);
  }
  await browser.close();
  await restoreStand();
  for (const problem of problems) console.log(`PROBLEM ${problem}`);
  process.exitCode = problems.length ? 1 : 0;
}

/** Opens a workspace's document list and returns the id of the first document titled so. */
export async function documentIdByTitle(page, organization, title) {
  await page.goto(`${BASE}/o/${organization}/w/main/documents`, { waitUntil: "networkidle" });
  const href = await page.getByRole("link", { name: title }).first().getAttribute("href");
  return href.split("/").pop();
}
