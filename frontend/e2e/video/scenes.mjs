// The product video's scenes, played on the demo stand by the lawyer of
// «Заря»: upload → check → a footnote to the law → automatic fix → a
// question to the norm. Each scene runs in the layout of its format
// (`wide` for the landscape cut, `narrow` for the vertical one) and wraps
// the part worth showing in `take.begin()` / `take.end()`.
import { resolve } from "node:path";

import { BASE, ROOT } from "../runner.mjs";
import { glide, pause } from "../landing/media.mjs";

const FILE = resolve(ROOT, "backend/demo/reference/politika-zarya.docx");
const KIND = "Политика обработки ПДн";
const QUESTION = "В какой срок нужно прекратить обработку после отзыва согласия?";
const FINDING = /Не указаны конкретные цели обработки/;
// A check of a document whose answers are cached takes seconds; a cold one
// waits for the model.
const CHECK_TIMEOUT = 300_000;

/** The title the uploaded copy gets: unique, so the scene finds its own row. */
export function uploadTitle(now = new Date()) {
  const time = now.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  return `Политика для сайта, ${time}`;
}

export const SCENES = [
  {
    id: "upload",
    card: { title: "Загрузите документ", note: "DOCX или PDF — скан тоже прочитаем" },
    async run(page, take, { title }) {
      await page.goto(`${BASE}/o/zarya/w/main/documents`, { waitUntil: "networkidle" });
      take.begin();
      await pause(page, 700);
      await page.getByRole("button", { name: "Загрузить" }).first().click();
      const dialog = page.getByRole("dialog");
      await pause(page, 600);
      await dialog.locator("input[type=file]").setInputFiles(FILE);
      await pause(page, 700);
      await dialog.getByRole("combobox", { name: "Вид документа" }).click();
      await pause(page, 400);
      await page.getByRole("option", { name: KIND }).click();
      await pause(page, 400);
      await dialog.getByRole("textbox", { name: "Название" }).click();
      await page.keyboard.type(title, { delay: 40 });
      await pause(page, 500);
      await dialog.getByRole("button", { name: "Загрузить" }).click();
      await page.getByRole("link", { name: title }).first().waitFor({ timeout: 60_000 });
      await pause(page, 1400);
      take.end();
    },
  },
  {
    id: "check",
    card: { title: "Проверка", note: "Оформление по ГОСТ и требования 152-ФЗ" },
    // Waiting for the model is sped up to this length.
    longest: 8,
    async run(page, take, { title }) {
      take.begin();
      await page.getByRole("link", { name: title }).first().click();
      await page
        .getByText(/^\d+ замечани/)
        .first()
        .waitFor({ timeout: CHECK_TIMEOUT });
      await pause(page, 1600);
      await glide(page, 320, 1800);
      await pause(page, 1200);
      take.end();
      await page.evaluate(() => window.scrollTo(0, 0));
    },
  },
  {
    id: "footnote",
    card: { title: "Сноска на закон", note: "Каждое замечание — с нормой и цитатой" },
    async run(page, take, { narrow }) {
      take.begin();
      await pause(page, 500);
      if (narrow) {
        await page.getByRole("button", { name: /^Замечания/ }).click();
        await pause(page, 900);
      }
      await page.getByRole("button", { name: FINDING }).first().click();
      await pause(page, 1200);
      if (narrow) await glide(page, 420, 2000, "[role=dialog] > div:last-child");
      else await glide(page, 420, 2000);
      await pause(page, 2200);
      take.end();
      if (narrow) await page.keyboard.press("Escape");
      await page.evaluate(() => window.scrollTo(0, 0));
    },
  },
  {
    id: "autofix",
    card: { title: "Исправление оформления", note: "Новая версия, исходный файл не меняется" },
    longest: 10,
    async run(page, take) {
      await pause(page, 400);
      take.begin();
      await page.getByRole("button", { name: "Исправить оформление" }).click();
      const dialog = page.getByRole("dialog");
      await dialog.getByText("Исправим").waitFor();
      await pause(page, 1600);
      await dialog.getByRole("button", { name: "Создать исправленную версию" }).click();
      const compare = page.getByRole("button", { name: /Было и стало/ });
      await compare.waitFor({ timeout: CHECK_TIMEOUT });
      await pause(page, 900);
      await compare.click();
      await pause(page, 2800);
      take.end();
    },
  },
  {
    id: "ask",
    card: { title: "Спросите норму", note: "Ответ только с цитатами из закона" },
    async run(page, take) {
      await page.goto(`${BASE}/o/zarya/ask`, { waitUntil: "networkidle" });
      take.begin();
      await pause(page, 600);
      await page.getByRole("textbox", { name: "Вопрос" }).click();
      await page.keyboard.type(QUESTION, { delay: 30 });
      await pause(page, 400);
      await page.keyboard.press("Enter");
      await page.getByRole("list", { name: "Цитаты из закона" }).waitFor({ timeout: 120_000 });
      await pause(page, 1000);
      await glide(page, 360, 2000);
      await pause(page, 2200);
      take.end();
    },
  },
];

export const INTRO = {
  title: "Сноска",
  note: "Проверка документов по 152-ФЗ и ГОСТ — со ссылкой на норму к каждому замечанию",
};
export const OUTRO = {
  title: "Попробуйте демо",
  note: "Вход в один клик: владелец, юрист, наблюдатель, оператор. Данные вымышлены.",
};
