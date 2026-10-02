// Shared by the screenshot sets: demo sign-in and the capture loop that
// shoots every screen in three viewports and both themes with headless
// Chromium (sound muted) and reports horizontal overflow and page errors.
import { mkdir, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
export const BASE = process.env.WEB_URL ?? "http://localhost:46300";
export const VIEWPORTS = {
  phone: { width: 390, height: 844 },
  tablet: { width: 768, height: 1024 },
  desktop: { width: 1280, height: 800 },
};
const THEMES = ["light", "dark"];
const SETTLE_MS = 700;

/** Demo passwords by email, read from the project's seed file. */
async function credentials() {
  const seed = await readFile(resolve(ROOT, "backend/demo/seed.yaml"), "utf8");
  const pairs = new Map();
  for (const match of seed.matchAll(
    /email: (\S+)\n\s+first_name: .*\n\s+last_name: .*\n\s+password: (\S+)/g,
  )) {
    pairs.set(match[1], match[2]);
  }
  return pairs;
}

async function signIn(browser, email, password) {
  const context = await browser.newContext({ viewport: VIEWPORTS.desktop });
  const page = await context.newPage();
  await page.goto(`${BASE}/`);
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
      if (screen.viewports && !screen.viewports.includes(viewport)) continue;
      for (const theme of THEMES) {
        const context = await browser.newContext({
          viewport: size,
          deviceScaleFactor: 1,
          colorScheme: theme,
          storageState: screen.user ? states[screen.user] : undefined,
          isMobile: viewport === "phone",
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
          await page.screenshot({ path: `${out}/${screen.name}--${viewport}-${theme}.png` });
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
  for (const problem of problems) console.log(`PROBLEM ${problem}`);
  process.exitCode = problems.length ? 1 : 0;
}

/** Opens a workspace's document list and returns the id of the first document titled so. */
export async function documentIdByTitle(page, organization, title) {
  await page.goto(`${BASE}/o/${organization}/w/main/documents`, { waitUntil: "networkidle" });
  const href = await page.getByRole("link", { name: title }).first().getAttribute("href");
  return href.split("/").pop();
}
