// Milestone 4: the landing and the demo entrance for guests, results with
// real legal findings of the model, a spent plan allowance, paginated logs
// and the remarks of the milestone 3 acceptance.
//   MILESTONE=m4 node e2e/screenshots.mjs
// The states a spent daily model allowance shows are in m4-limit.mjs.
import { resolve } from "node:path";

import { BASE, ROOT, documentIdByTitle } from "../runner.mjs";

const OWNER = "polyarnaya-zvezda";
const ZARYA = "zarya";
const SOKOLOVA = "sokolova";
const POLICY = "Политика обработки персональных данных";
const FINDING = /Не указаны конкретные цели обработки/;
const QUESTION = "В какой срок нужно прекратить обработку после отзыва согласия?";
const CONSENT = "Согласие на обработку персональных данных клиентов";
const MAILING = "Согласие на рассылку новостей";
const PAUSE = (page, ms) => page.waitForTimeout(ms);

async function open(page, path) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
}

/** Scrolls a landing section under the sticky header. */
async function toSection(page, selector) {
  await page.evaluate((target) => {
    document.querySelector(target).scrollIntoView({ block: "start" });
    window.scrollBy(0, -64);
  }, selector);
  await PAUSE(page, 400);
}

async function bff(page, path, init) {
  return page.evaluate(
    async ({ path, init }) => {
      const response = await fetch(`/bff/api/v1${path}`, init);
      return { status: response.status, body: response.ok ? await response.json() : null };
    },
    { path, init },
  );
}

/** The latest conversation of the lawyer, asked once if there is none. */
async function conversationId(page) {
  await open(page, `/o/${ZARYA}/ask`);
  const listed = await bff(page, `/organizations/${ZARYA}/ask/conversations`);
  if (listed.body?.items?.length) return listed.body.items[0].id;
  await page.getByRole("textbox", { name: "Вопрос" }).fill(QUESTION);
  await page.keyboard.press("Enter");
  await page.getByRole("list", { name: "Цитаты из закона" }).waitFor({ timeout: 120_000 });
  return new URL(page.url()).pathname.split("/").pop();
}

/** Uploads a reference document into «ИП Соколова» unless it is there; returns its id. */
async function uploadOnce(page, { title, file, kind }) {
  await open(page, `/o/${SOKOLOVA}/w/main/documents`);
  if (!(await page.getByRole("link", { name: title }).count())) {
    await page.getByRole("button", { name: "Загрузить" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog
      .locator("input[type=file]")
      .setInputFiles(resolve(ROOT, `backend/demo/reference/${file}`));
    await dialog.getByRole("combobox", { name: "Вид документа" }).click();
    await page.getByRole("option", { name: kind }).click();
    await dialog.getByRole("textbox", { name: "Название" }).fill(title);
    await dialog.getByRole("button", { name: "Загрузить" }).click();
    await page.getByRole("link", { name: title }).first().waitFor({ timeout: 60_000 });
  }
  return documentIdByTitle(page, SOKOLOVA, title);
}

/**
 * Spends the Start plan's checks of «ИП Соколова»: one document checked
 * again until the plan refuses, then the next upload finds no check left.
 * Model answers are cached, so this costs no model requests; the nightly
 * reset gives the allowance back. Returns the document left unchecked.
 */
async function spendChecks(page) {
  const kind = "Согласие на обработку ПДн";
  const id = await uploadOnce(page, { title: CONSENT, file: "soglasie-zarya.docx", kind });
  const checks = `/organizations/${SOKOLOVA}/documents/${id}/versions/1/checks`;
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const run = (await bff(page, `${checks}/latest`)).body?.run;
    if (!run || run.status === "queued" || run.status === "running") {
      await PAUSE(page, 1500);
      continue;
    }
    // The plan refuses a check over its allowance with 402.
    if ((await bff(page, checks, { method: "POST" })).status === 402) break;
    await PAUSE(page, 1200);
  }
  return uploadOnce(page, { title: MAILING, file: "soglasie-rassylka.docx", kind });
}

/** Test events to the demo receiver until the log has more than one page. */
async function fillDeliveries(page) {
  for (let sent = 0; sent < 8; sent += 1) {
    if ((await page.getByRole("button", { name: "Показать ещё" }).count()) > 0) return;
    await page.getByRole("button", { name: "Тестовое событие" }).click();
    await PAUSE(page, 1500);
    await page.reload({ waitUntil: "networkidle" });
  }
}

export const SCREENS = [
  { name: "01-landing", run: (page) => open(page, "/") },
  {
    name: "02-landing-showcase",
    run: async (page) => {
      await open(page, "/");
      await toSection(page, "#features");
    },
  },
  {
    name: "03-landing-numbers",
    run: async (page) => {
      await open(page, "/");
      await toSection(page, "#numbers-title");
    },
  },
  {
    name: "04-landing-pricing",
    run: async (page) => {
      await open(page, "/");
      await toSection(page, "#pricing");
    },
  },
  { name: "05-demo", run: (page) => open(page, "/demo") },
  {
    name: "06-how-we-check-models",
    run: async (page) => {
      await open(page, "/how-we-check");
      await page.getByRole("heading", { name: "Выбор модели" }).scrollIntoViewIfNeeded();
    },
  },
  {
    name: "07-result-legal-finding",
    user: "lawyer",
    run: async (page, { viewport }) => {
      const id = await documentIdByTitle(page, ZARYA, POLICY);
      await open(page, `/o/${ZARYA}/documents/${id}?v=1`);
      if (viewport !== "desktop") {
        await page.getByRole("button", { name: /^Замечания/ }).click();
        await page.getByRole("dialog").waitFor();
      }
      await page.getByRole("button", { name: FINDING }).first().click();
      await PAUSE(page, 500);
    },
  },
  {
    name: "08-ask-answer",
    user: "lawyer",
    run: async (page) => {
      const id = await conversationId(page);
      await open(page, `/o/${ZARYA}/ask/${id}`);
      await page.getByRole("list", { name: "Цитаты из закона" }).waitFor();
    },
  },
  {
    // The plan's checks are spent: the run says so and leads to the plan.
    name: "09-quota-spent-check",
    user: "sokolova",
    run: async (page) => {
      const id = await spendChecks(page);
      await open(page, `/o/${SOKOLOVA}/documents/${id}`);
      await page.getByText("Лимит проверок на этот месяц исчерпан").waitFor();
    },
  },
  {
    name: "10-quota-spent-billing",
    user: "sokolova",
    run: (page) => open(page, `/o/${SOKOLOVA}/settings/billing`),
  },
  {
    // Remark: the ledger is paginated (28 entries, 20 a page).
    name: "11-ledger-pages",
    user: "zaryaOwner",
    run: async (page) => {
      await open(page, `/o/${ZARYA}/settings/billing`);
      await page.getByRole("button", { name: "Показать ещё" }).scrollIntoViewIfNeeded();
    },
  },
  {
    // Remark: the delivery log is paginated.
    name: "12-deliveries-pages",
    user: "owner",
    run: async (page) => {
      await open(page, `/o/${OWNER}/settings/webhooks`);
      await page.getByRole("link", { name: "Демо-приёмник" }).click();
      await page.getByText("Доставки").first().waitFor();
      await page.waitForLoadState("networkidle");
      await fillDeliveries(page);
      await page.getByRole("button", { name: "Показать ещё" }).scrollIntoViewIfNeeded();
    },
  },
  {
    // Remark: role selects keep one width in the member list.
    name: "13-members-roles",
    user: "owner",
    run: (page) => open(page, `/o/${OWNER}/settings/members`),
  },
  {
    // Remark: room around the rows of the before/after sheet.
    name: "14-autofix-compare",
    user: "lawyer",
    run: async (page) => {
      const id = await documentIdByTitle(page, ZARYA, POLICY);
      await open(page, `/o/${ZARYA}/documents/${id}`);
      if (!(await page.getByText(/Оформление исправлено автоматически/).count())) {
        await page.getByRole("button", { name: "Исправить оформление" }).click();
        await page.getByRole("button", { name: "Создать исправленную версию" }).click();
        await page.waitForURL(/v=2/);
      }
      await page.getByRole("button", { name: /Было и стало/ }).waitFor({ timeout: 120_000 });
      await page.getByRole("button", { name: /Было и стало/ }).click();
      await page.getByRole("dialog").waitFor();
    },
  },
  {
    // The model in use and the requests left of today's allowance.
    name: "15-platform-system",
    user: "operator",
    run: (page) => open(page, "/platform/system"),
  },
];

export const USERS = {
  owner: "kovaleva@polyarnaya-zvezda.example",
  zaryaOwner: "ershov@zarya.example",
  lawyer: "polyakova@zarya.example",
  sokolova: "sokolova@sokolova.example",
  operator: "operator@snoska.example",
};
