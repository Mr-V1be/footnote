// Before/after of the milestone 2 acceptance remarks:
//   OUT_DIR=docs/screenshots/m3/fixes SUFFIX=before MILESTONE=m3-fixes node e2e/screenshots.mjs
import { BASE, documentIdByTitle } from "../runner.mjs";

const ZARYA = "zarya";

async function openDocument(page, title) {
  const id = await documentIdByTitle(page, ZARYA, title);
  await page.goto(`${BASE}/o/${ZARYA}/documents/${id}`, { waitUntil: "networkidle" });
}

export const SCREENS = [
  {
    // Remark 1: a rule broken in most paragraphs lit up the whole text.
    name: "1-highlight-policy",
    user: "polyakova",
    viewports: ["phone", "desktop"],
    run: async (page) => {
      await openDocument(page, "Политика обработки персональных данных");
      await page.locator("#block-6").scrollIntoViewIfNeeded();
    },
  },
  {
    name: "1-highlight-consent",
    user: "polyakova",
    viewports: ["phone", "desktop"],
    run: async (page) => {
      await openDocument(page, "Согласие участника программы лояльности");
      await page.locator("#block-2").scrollIntoViewIfNeeded();
    },
  },
  {
    // After: the document-wide finding opened shows its places for a while.
    name: "1-highlight-places",
    user: "polyakova",
    viewports: ["phone", "desktop"],
    run: async (page, { viewport }) => {
      await openDocument(page, "Согласие участника программы лояльности");
      if (viewport !== "desktop") {
        await page.getByRole("button", { name: /^Замечания/ }).click();
        await page.getByRole("dialog").waitFor();
      }
      await page.getByRole("button", { name: /Кегль основного текста/ }).first().click();
      await page.getByRole("button", { name: "К первому месту" }).click();
      await page.waitForTimeout(600);
    },
  },
  {
    // Remark 2: the phone's bottom bar at 360 and 390 px.
    name: "2-bottom-bar",
    user: "polyakova",
    viewports: ["small", "phone"],
    run: async (page) => openDocument(page, "Политика обработки персональных данных"),
  },
];

export const USERS = { polyakova: "polyakova@zarya.example" };
