// Captures every screen of the milestone in three viewports and both themes
// with headless Chromium, and reports horizontal overflow.
//
//   node e2e/screenshots.mjs            all screens into docs/screenshots/m1
//   SCREENS=viewer node e2e/...         only screens whose name contains "viewer"
//
// Demo credentials are read from the project's seed file.
import { mkdir, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const BASE = process.env.WEB_URL ?? "http://localhost:46300";
const OUT = resolve(root, process.env.OUT_DIR ?? "docs/screenshots/m1");
const ONLY = process.env.SCREENS;
const VIEWPORTS = {
  phone: { width: 390, height: 844 },
  tablet: { width: 768, height: 1024 },
  desktop: { width: 1280, height: 800 },
};
const THEMES = ["light", "dark"];
const ORG = "polyarnaya-zvezda";
const SETTLE_MS = 700;

async function credentials() {
  const seed = await readFile(resolve(root, "backend/demo/seed.yaml"), "utf8");
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

async function documentIdByTitle(page, title) {
  await page.goto(`${BASE}/o/${ORG}/w/main/documents`, { waitUntil: "networkidle" });
  const href = await page.getByRole("link", { name: title }).first().getAttribute("href");
  return href.split("/").pop();
}

/** Each screen prepares the page; the runner captures it afterwards. */
const SCREENS = [
  {
    name: "01-documents",
    user: "orlov",
    run: async (page) =>
      page.goto(`${BASE}/o/${ORG}/w/main/documents`, { waitUntil: "networkidle" }),
  },
  {
    name: "02-documents-upload",
    user: "orlov",
    run: async (page, { viewport }) => {
      await page.goto(`${BASE}/o/${ORG}/w/main/documents`, { waitUntil: "networkidle" });
      const button =
        viewport === "desktop"
          ? page.locator("header").getByRole("button", { name: "Загрузить" })
          : page.getByRole("button", { name: "Загрузить" }).last();
      await button.click();
      await page.getByRole("dialog").waitFor();
    },
  },
  {
    name: "03-documents-loading",
    user: "orlov",
    run: async (page) => {
      await page.goto(`${BASE}/o/${ORG}/w/main/documents`, { waitUntil: "networkidle" });
      await page.route("**/bff/api/v1/organizations/*/workspaces/*/documents**", () => {});
      await page.getByRole("searchbox").fill("политика");
      await page.waitForTimeout(600);
    },
  },
  {
    name: "04-documents-error",
    user: "orlov",
    run: async (page) => {
      await page.goto(`${BASE}/o/${ORG}/w/main/documents`, { waitUntil: "networkidle" });
      await page.route("**/bff/api/v1/organizations/*/workspaces/*/documents**", (route) =>
        route.fulfill({
          status: 503,
          contentType: "application/problem+json",
          body: '{"code":"dependency_unavailable","status":503,"title":"x"}',
        }),
      );
      await page.getByRole("searchbox").fill("договор");
      await page.getByRole("alert").waitFor({ timeout: 15_000 });
    },
  },
  {
    name: "05-documents-no-matches",
    user: "orlov",
    run: async (page) =>
      page.goto(`${BASE}/o/${ORG}/w/main/documents?q=${encodeURIComponent("устав")}`, {
        waitUntil: "networkidle",
      }),
  },
  {
    name: "06-documents-empty",
    user: "sokolova",
    run: async (page) =>
      page.goto(`${BASE}/o/sokolova/w/main/documents`, { waitUntil: "networkidle" }),
  },
  {
    name: "07-documents-read-only",
    user: "belov",
    run: async (page) =>
      page.goto(`${BASE}/o/${ORG}/w/main/documents`, { waitUntil: "networkidle" }),
  },
  {
    name: "08-viewer",
    user: "orlov",
    run: async (page) => {
      const id = await documentIdByTitle(
        page,
        "Политика в отношении обработки персональных данных",
      );
      await page.goto(`${BASE}/o/${ORG}/documents/${id}`, { waitUntil: "networkidle" });
    },
  },
  {
    name: "09-viewer-scan",
    user: "orlov",
    run: async (page) => {
      const id = await documentIdByTitle(page, "Приказ № 7-ОД");
      await page.goto(`${BASE}/o/${ORG}/documents/${id}`, { waitUntil: "networkidle" });
    },
  },
  {
    name: "10-viewer-outline",
    user: "orlov",
    run: async (page) => {
      const id = await documentIdByTitle(
        page,
        "Политика в отношении обработки персональных данных",
      );
      await page.goto(`${BASE}/o/${ORG}/documents/${id}`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: "Содержание" }).click();
      await page.getByRole("dialog").waitFor();
    },
  },
  {
    name: "11-viewer-requisites",
    user: "orlov",
    viewports: ["phone", "tablet"],
    run: async (page) => {
      const id = await documentIdByTitle(page, "Договор поручения");
      await page.goto(`${BASE}/o/${ORG}/documents/${id}`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: /Реквизиты/ }).click();
      await page.getByRole("dialog").waitFor();
    },
  },
  {
    name: "12-viewer-versions",
    user: "orlov",
    run: async (page) => {
      const id = await documentIdByTitle(
        page,
        "Положение об обработке персональных данных работников",
      );
      await page.goto(`${BASE}/o/${ORG}/documents/${id}`, { waitUntil: "networkidle" });
      await page.getByRole("combobox", { name: "Версия документа" }).click();
      await page.getByRole("listbox").waitFor();
    },
  },
  {
    name: "13-viewer-not-found",
    user: "orlov",
    run: async (page) =>
      page.goto(`${BASE}/o/${ORG}/documents/00000000-0000-7000-8000-000000000000`, {
        waitUntil: "networkidle",
      }),
  },
  {
    name: "14-no-access",
    user: "orlov",
    run: async (page) => page.goto(`${BASE}/o/rechnoy-port`, { waitUntil: "networkidle" }),
  },
  {
    name: "15-user-menu",
    user: "orlov",
    run: async (page) => {
      await page.goto(`${BASE}/o/${ORG}/w/main/documents`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: "Профиль и настройки" }).first().click();
      await page.getByRole("menu").waitFor();
    },
  },
];

const USERS = {
  orlov: "orlov@polyarnaya-zvezda.example",
  belov: "belov@polyarnaya-zvezda.example",
  sokolova: "sokolova@sokolova.example",
};

async function main() {
  await mkdir(OUT, { recursive: true });
  const passwords = await credentials();
  const browser = await chromium.launch({ args: ["--mute-audio"] });
  const states = {};
  const screens = SCREENS.filter((screen) => !ONLY || screen.name.includes(ONLY));
  for (const user of new Set(screens.map((screen) => screen.user))) {
    states[user] = await signIn(browser, USERS[user], passwords.get(USERS[user]));
  }
  const problems = [];
  for (const screen of screens) {
    for (const [viewport, size] of Object.entries(VIEWPORTS)) {
      if (screen.viewports && !screen.viewports.includes(viewport)) continue;
      for (const theme of THEMES) {
        const context = await browser.newContext({
          viewport: size,
          deviceScaleFactor: 1,
          colorScheme: theme,
          storageState: states[screen.user],
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
          await page.screenshot({ path: `${OUT}/${screen.name}--${viewport}-${theme}.png` });
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

await main();
