// Milestone 4, the states of a spent daily model allowance. Captured on a
// day the free model's requests have run out (they are real states, not
// answers drawn by the script):
//   MILESTONE=m4-limit OUT_DIR=docs/screenshots/m4 node e2e/screenshots.mjs
// The document is a fresh one, so no cached answer can stand in for the model.
import { resolve } from "node:path";

import { BASE, ROOT, documentIdByTitle } from "../runner.mjs";

const ZARYA = "zarya";
const FRESH = "Согласие участника дегустации";

async function open(page, path) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
}

async function freshDocument(page) {
  await open(page, `/o/${ZARYA}/w/main/documents`);
  if (!(await page.getByRole("link", { name: FRESH }).count())) {
    await page.getByRole("button", { name: "Загрузить" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog
      .locator("input[type=file]")
      .setInputFiles(resolve(ROOT, "frontend/e2e/fixtures/soglasie-degustaciya.docx"));
    await dialog.getByRole("combobox", { name: "Вид документа" }).click();
    await page.getByRole("option", { name: "Согласие на обработку ПДн" }).click();
    await dialog.getByRole("textbox", { name: "Название" }).fill(FRESH);
    await dialog.getByRole("button", { name: "Загрузить" }).click();
    await page.getByRole("link", { name: FRESH }).first().waitFor({ timeout: 60_000 });
  }
  return documentIdByTitle(page, ZARYA, FRESH);
}

export const SCREENS = [
  {
    name: "16-ask-daily-limit",
    user: "lawyer",
    run: async (page) => {
      await open(page, `/o/${ZARYA}/ask`);
      await page.getByText("Дневной лимит модели исчерпан").waitFor();
    },
  },
  {
    // Rules ran; the legal requirements wait and run again on their own.
    name: "17-check-waiting-for-model",
    user: "lawyer",
    run: async (page) => {
      const id = await freshDocument(page);
      await open(page, `/o/${ZARYA}/documents/${id}`);
      await page
        .getByText(/Дневной лимит запросов к модели исчерпан/)
        .waitFor({ timeout: 120_000 });
    },
  },
  {
    name: "18-platform-system-limit",
    user: "operator",
    run: (page) => open(page, "/platform/system"),
  },
];

export const USERS = {
  lawyer: "polyakova@zarya.example",
  operator: "operator@snoska.example",
};
