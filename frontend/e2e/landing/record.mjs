// Records the landing page's media from the running stand: short silent
// loops of the product (H.264 + WebP poster) and stills, in both themes, in
// one interface language (a set per language: public/landing/<locale>).
//   node e2e/landing/record.mjs                   everything, in Russian
//   LOCALE=en node e2e/landing/record.mjs         everything, in English
//   CLIPS=ask,result node e2e/landing/record.mjs
// Needs the stand with the seed and checked documents (make demo-refresh).
import { mkdir, rm } from "node:fs/promises";
import { resolve } from "node:path";

import { chromium } from "playwright";

import {
  BASE,
  LOCALE,
  ROOT,
  checkTitle,
  credentials,
  literally,
  messages,
  restoreStand,
  signIn,
} from "../runner.mjs";
import { encodeLoop, encodeStill, glide, launchRecorder, pause, recording } from "./media.mjs";

const OUT = resolve(ROOT, "frontend/public/landing", LOCALE);
const WORK = resolve(ROOT, ".run/landing-media", LOCALE);
const THEMES = ["light", "dark"];
const LAPTOP = { width: 1280, height: 800 };
const PHONE = { width: 390, height: 844 };
const QUESTIONS = {
  ru: "В какой срок нужно прекратить обработку после отзыва согласия?",
  en: "How soon must processing stop after consent is withdrawn?",
};
const m = await messages();
const DATE_FINDING = literally(await checkTitle("formatting.date_format"));
const FONT_FINDING = literally(await checkTitle("formatting.font_size"));

/**
 * The autofix clip shows version 2 of the policy, the automatic fix of
 * version 1: made here on a freshly seeded stand.
 */
async function ensureFixed(page, organization, id) {
  await page.goto(`${BASE}/o/${organization}/documents/${id}`, { waitUntil: "networkidle" });
  const compare = page.getByRole("button", { name: literally(m.autofix.compare) });
  if ((await compare.count()) > 0) return;
  await page.getByRole("button", { name: m.checks.summary.autofix }).click();
  await page.getByRole("dialog").getByRole("button", { name: m.autofix.apply }).click();
  await compare.waitFor({ timeout: 300_000 });
}

async function documentId(page, organization, title) {
  await page.goto(`${BASE}/o/${organization}/w/main/documents`, { waitUntil: "networkidle" });
  const href = await page.getByRole("link", { name: title }).first().getAttribute("href");
  return href.split("/").pop();
}

const CLIPS = {
  result: {
    user: "lawyer",
    viewport: LAPTOP,
    width: 1280,
    async run(page, { policy }) {
      await page.goto(`${BASE}/o/zarya/documents/${policy}?v=1`, { waitUntil: "networkidle" });
      await pause(page, 600);
      return async () => {
        await pause(page, 900);
        await glide(page, 520, 3200);
        await pause(page, 700);
        await page.getByRole("button", { name: DATE_FINDING }).first().click();
        await pause(page, 1600);
        await glide(page, -520, 2200);
        await pause(page, 600);
      };
    },
  },
  "result-phone": {
    user: "lawyer",
    viewport: PHONE,
    scale: 2,
    mobile: true,
    width: 390,
    async run(page, { policy }) {
      await page.goto(`${BASE}/o/zarya/documents/${policy}?v=1`, { waitUntil: "networkidle" });
      await pause(page, 600);
      return async () => {
        await pause(page, 700);
        await glide(page, 640, 2800);
        await pause(page, 500);
        const findings = new RegExp(`^${literally(m.checks.findings).source}`);
        await page.getByRole("button", { name: findings }).click();
        await pause(page, 2400);
      };
    },
  },
  footnotes: {
    user: "lawyer",
    viewport: LAPTOP,
    width: 1280,
    async run(page, { policy }) {
      await page.goto(`${BASE}/o/zarya/documents/${policy}?v=1`, { waitUntil: "networkidle" });
      await pause(page, 600);
      return async () => {
        await pause(page, 700);
        await page.getByRole("button", { name: FONT_FINDING }).first().click();
        await pause(page, 900);
        await page.getByRole("button", { name: m.checks.firstPlace }).click();
        await pause(page, 1500);
        await glide(page, 360, 2400);
        await pause(page, 900);
      };
    },
  },
  autofix: {
    user: "lawyer",
    viewport: PHONE,
    scale: 2,
    mobile: true,
    width: 390,
    async run(page, { policy }) {
      await page.goto(`${BASE}/o/zarya/documents/${policy}?v=2`, { waitUntil: "networkidle" });
      await pause(page, 600);
      return async () => {
        await pause(page, 900);
        await page.getByRole("button", { name: literally(m.autofix.compare) }).click();
        await pause(page, 1800);
        await glide(page, 260, 1800, "[role=dialog] > div:last-child");
        await pause(page, 1400);
      };
    },
  },
  ask: {
    user: "lawyer",
    viewport: PHONE,
    scale: 2,
    poster: "end",
    mobile: true,
    width: 390,
    async run(page) {
      await page.goto(`${BASE}/o/zarya/ask`, { waitUntil: "networkidle" });
      await pause(page, 600);
      return async () => {
        await pause(page, 500);
        await page.getByRole("textbox", { name: m.ask.question }).click();
        await page.keyboard.type(QUESTIONS[LOCALE], { delay: 35 });
        await pause(page, 400);
        await page.keyboard.press("Enter");
        await page.getByRole("list", { name: m.ask.citations }).waitFor({ timeout: 120_000 });
        await pause(page, 900);
        await glide(page, 360, 2200);
        await pause(page, 1600);
      };
    },
  },
};

const STILLS = {
  "step-upload": {
    user: "lawyer",
    viewport: { width: 1200, height: 800 },
    async run(page) {
      await page.goto(`${BASE}/o/zarya/w/main/documents`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: m.documents.upload }).first().click();
      await page
        .locator("[role=dialog] input[type=file]")
        .setInputFiles(resolve(ROOT, "backend/demo/reference/politika-zarya.docx"));
      await pause(page, 500);
    },
  },
  "step-check": {
    user: "lawyer",
    viewport: { width: 1200, height: 800 },
    async run(page, { policy }) {
      await page.goto(`${BASE}/o/zarya/documents/${policy}?v=1`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: DATE_FINDING }).first().click();
      await pause(page, 600);
    },
  },
  "step-fix": {
    user: "lawyer",
    viewport: { width: 1200, height: 800 },
    async run(page, { policy }) {
      await page.goto(`${BASE}/o/zarya/documents/${policy}?v=1`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: m.checks.summary.autofix }).click();
      await page.getByRole("dialog").getByText(m.autofix.planned).waitFor();
      await pause(page, 400);
    },
  },
  "tile-roles": {
    user: "owner",
    viewport: { width: 1200, height: 680 },
    async run(page) {
      await page.goto(`${BASE}/o/polyarnaya-zvezda/settings/workspaces`, {
        waitUntil: "networkidle",
      });
      await page.getByRole("link", { name: "Кадры" }).click();
      await page.waitForLoadState("networkidle");
    },
  },
  "tile-audit": {
    user: "owner",
    viewport: { width: 1200, height: 680 },
    async run(page) {
      await page.goto(`${BASE}/o/polyarnaya-zvezda/settings/audit`, { waitUntil: "networkidle" });
    },
  },
};

const USERS = { lawyer: "polyakova@zarya.example", owner: "kovaleva@polyarnaya-zvezda.example" };

function wanted(name) {
  const filter = (process.env.CLIPS ?? "").split(",").filter(Boolean);
  return filter.length === 0 || filter.some((term) => name.includes(term));
}

const browser = await launchRecorder(chromium);
const passwords = await credentials();
const states = {};
for (const [role, email] of Object.entries(USERS)) {
  states[role] = await signIn(browser, email, passwords.get(email));
}
await mkdir(OUT, { recursive: true });
const probe = await browser.newContext({ storageState: states.lawyer });
const probePage = await probe.newPage();
const policy = await documentId(probePage, "zarya", "Политика обработки персональных данных");
await ensureFixed(probePage, "zarya", policy);
await probe.close();
const facts = { policy };

for (const theme of THEMES) {
  for (const [name, clip] of Object.entries(CLIPS)) {
    if (!wanted(name)) continue;
    const take = await recording(browser, {
      viewport: clip.viewport,
      scale: clip.scale ?? 1,
      theme,
      storageState: states[clip.user],
      dir: resolve(WORK, `${name}-${theme}`),
      mobile: clip.mobile ?? false,
    });
    const play = await clip.run(take.page, facts);
    take.mark();
    await play();
    await encodeLoop(await take.finish(), resolve(OUT, `${name}-${theme}`), {
      width: clip.width * (clip.scale ?? 1) > 1280 ? 1280 : clip.width * (clip.scale ?? 1),
      poster: clip.poster,
    });
    console.log(`clip ${name} ${theme}`);
  }
  for (const [name, still] of Object.entries(STILLS)) {
    if (!wanted(name)) continue;
    const context = await browser.newContext({
      viewport: still.viewport,
      deviceScaleFactor: 1,
      colorScheme: theme,
      storageState: states[still.user],
    });
    await context.addCookies([{ name: "snoska_theme", value: theme, url: BASE }]);
    const page = await context.newPage();
    await still.run(page, facts);
    const png = resolve(WORK, `${name}-${theme}.png`);
    await mkdir(WORK, { recursive: true });
    await page.screenshot({ path: png });
    await encodeStill(png, resolve(OUT, `${name}-${theme}`), { width: still.viewport.width });
    await context.close();
    console.log(`still ${name} ${theme}`);
  }
}
await browser.close();
await rm(WORK, { recursive: true, force: true });
await restoreStand();
