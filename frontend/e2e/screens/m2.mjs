// Milestone 2: the check — results as footnotes, review, progress and the
// methodology page. Captured against the demo stand after `snoska demo seed`
// with no model API connected, so the legal checks honestly report that.
//
// The "queued" screens need the worker stopped, so the run stays queued:
//   SCREENS=queued node e2e/screenshots.mjs, then the rest with SCREENS='!queued'.
import { BASE, documentIdByTitle } from "../runner.mjs";

const ZARYA = "zarya";
const POLAR = "polyarnaya-zvezda";
const POLICY = "Политика обработки персональных данных";
const ORDER = "Приказ о назначении ответственного за ПДн гостей";

async function openDocument(page, organization, title) {
  const id = await documentIdByTitle(page, organization, title);
  await page.goto(`${BASE}/o/${organization}/documents/${id}`, { waitUntil: "networkidle" });
  return id;
}

function placeCard(page) {
  return page.getByRole("article").filter({ hasText: "Не указано место" });
}

/** Takes a review action and waits until the server has stored it. */
async function decide(card, action) {
  const page = card.page();
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes("/findings/") && response.request().method() === "PATCH",
    ),
    card.getByRole("button", { name: action }).click(),
  ]);
}

/** On narrow screens the notes live in a bottom sheet opened from the bottom bar. */
async function openNotes(page, viewport) {
  if (viewport === "desktop") return;
  await page.getByRole("button", { name: /^Замечания/ }).click();
  await page.getByRole("dialog").waitFor();
}

export const SCREENS = [
  {
    name: "00-login",
    run: async (page) => {
      await page.goto(`${BASE}/`);
      await page.waitForSelector("#username");
    },
  },
  {
    name: "01-documents-checked",
    user: "polyakova",
    run: async (page) =>
      page.goto(`${BASE}/o/${ZARYA}/w/main/documents`, { waitUntil: "networkidle" }),
  },
  {
    name: "02-documents-clean",
    user: "orlov",
    run: async (page) =>
      page.goto(`${BASE}/o/${POLAR}/w/main/documents`, { waitUntil: "networkidle" }),
  },
  {
    name: "03-result",
    user: "polyakova",
    run: async (page) => openDocument(page, ZARYA, POLICY),
  },
  {
    name: "04-result-selected",
    user: "polyakova",
    run: async (page) => {
      await openDocument(page, ZARYA, ORDER);
      await page.locator("sup a").nth(2).click();
      await page.waitForTimeout(400);
    },
  },
  {
    name: "05-result-filters",
    user: "polyakova",
    run: async (page, { viewport }) => {
      await openDocument(page, ZARYA, ORDER);
      await openNotes(page, viewport);
      await page.getByRole("button", { name: "Серьёзность" }).click();
      await page.getByRole("menu").waitFor();
    },
  },
  {
    name: "06-result-reviewed",
    user: "polyakova",
    run: async (page, { viewport }) => {
      await openDocument(page, ZARYA, ORDER);
      await openNotes(page, viewport);
      // A finding about the whole document: one line in the margin until opened.
      await page.getByRole("button", { name: /Не указано место/ }).click();
      // A run interrupted earlier may have left it decided: start from "open".
      if (await placeCard(page).getByRole("button", { name: "Вернуть в работу" }).count()) {
        await decide(placeCard(page), "Вернуть в работу");
      }
      await decide(placeCard(page), "Принять");
      await placeCard(page).getByText("Принято").first().waitFor();
    },
    // Put the finding back as it was, so every capture starts from the same state.
    after: async (page) => decide(placeCard(page), "Вернуть в работу"),
  },
  {
    name: "07-result-queued",
    user: "polyakova",
    run: async (page) => {
      const id = await documentIdByTitle(page, ZARYA, "Согласие участника");
      await page.request.post(
        `${BASE}/bff/api/v1/organizations/${ZARYA}/documents/${id}/versions/1/checks`,
      );
      await page.goto(`${BASE}/o/${ZARYA}/documents/${id}`, { waitUntil: "networkidle" });
    },
  },
  {
    name: "07-documents-queued",
    user: "polyakova",
    run: async (page) =>
      page.goto(`${BASE}/o/${ZARYA}/w/main/documents`, { waitUntil: "networkidle" }),
  },
  {
    name: "08-result-clean",
    user: "orlov",
    run: async (page) =>
      openDocument(page, POLAR, "Политика в отношении обработки персональных данных"),
  },
  {
    name: "09-result-failed",
    user: "polyakova",
    run: async (page) => {
      // The failed state of a run, shown on a real report with its status replaced.
      await page.route(
        "**/bff/api/v1/organizations/*/documents/*/versions/*/checks/latest",
        async (route) => {
          const response = await route.fetch();
          const report = await response.json();
          report.run = { ...report.run, status: "failed", failureCode: "internal_error" };
          await route.fulfill({ response, json: { ...report, results: [], findings: [] } });
        },
      );
      await openDocument(page, ZARYA, "Положение об обработке");
    },
  },
  {
    name: "10-result-requisites",
    user: "polyakova",
    run: async (page, { viewport }) => {
      await openDocument(page, ZARYA, POLICY);
      if (viewport === "desktop") {
        await page.getByRole("radio", { name: "Реквизиты" }).click();
      } else {
        await page.getByRole("button", { name: /Реквизиты/ }).click();
        await page.getByRole("dialog").waitFor();
      }
    },
  },
  {
    name: "11-methodology",
    user: "orlov",
    run: async (page) => page.goto(`${BASE}/o/${POLAR}/methodology`, { waitUntil: "networkidle" }),
  },
  {
    name: "12-methodology-consent",
    user: "orlov",
    run: async (page) => {
      await page.goto(`${BASE}/o/${POLAR}/methodology`, { waitUntil: "networkidle" });
      await page.getByRole("combobox", { name: "Вид документа" }).click();
      await page.getByRole("option", { name: "Согласие на обработку ПДн" }).click();
      await page.getByRole("heading", { name: /Проверки/ }).scrollIntoViewIfNeeded();
    },
  },
];

export const USERS = {
  orlov: "orlov@polyarnaya-zvezda.example",
  polyakova: "polyakova@zarya.example",
};
