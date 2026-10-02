// Milestone 1: documents, the viewer and access states.
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { BASE, documentIdByTitle, ROOT } from "../runner.mjs";

const ORG = "polyarnaya-zvezda";
const PORT_ORG = "rechnoy-port";
const QUEUED_TITLE = "Приказ о назначении ответственного (скан)";
let queuedDocument = null;

/** Uploads one document through the web server once per run and returns its id. */
async function ensureQueuedDocument(page) {
  if (queuedDocument) return queuedDocument;
  const file = await readFile(
    resolve(ROOT, "backend/demo/documents/polyarnaya-zvezda/prikaz-7-od.pdf"),
  );
  const response = await page.request.post(
    `${BASE}/bff/api/v1/organizations/${PORT_ORG}/workspaces/main/documents`,
    {
      headers: { "Idempotency-Key": `screenshots-${Date.now()}` },
      multipart: {
        file: { name: "prikaz-skan.pdf", mimeType: "application/pdf", buffer: file },
        kind: "order",
        title: QUEUED_TITLE,
      },
    },
  );
  queuedDocument = (await response.json()).documentId;
  return queuedDocument;
}

/** Each screen prepares the page; the runner captures it afterwards. */
export const SCREENS = [
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
    // Processing states are real: run this screen with the worker stopped,
    // so the uploaded document stays queued while it is captured.
    name: "03-documents-processing",
    user: "lebedev",
    run: async (page) => {
      await ensureQueuedDocument(page);
      await page.goto(`${BASE}/o/${PORT_ORG}/w/main/documents`, { waitUntil: "networkidle" });
    },
  },
  {
    name: "03-viewer-processing",
    user: "lebedev",
    run: async (page) => {
      const id = await ensureQueuedDocument(page);
      await page.goto(`${BASE}/o/${PORT_ORG}/documents/${id}`, { waitUntil: "networkidle" });
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
          body: '{"code":"dependency_unavailable","status":503,"title":"Service Unavailable"}',
        }),
      );
      await page.getByRole("searchbox").fill("договор");
      await page.getByText("Не удалось загрузить документы").waitFor({ timeout: 20_000 });
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
        ORG,
        "Политика в отношении обработки персональных данных",
      );
      await page.goto(`${BASE}/o/${ORG}/documents/${id}`, { waitUntil: "networkidle" });
    },
  },
  {
    name: "09-viewer-scan",
    user: "orlov",
    run: async (page) => {
      const id = await documentIdByTitle(page, ORG, "Приказ № 7-ОД");
      await page.goto(`${BASE}/o/${ORG}/documents/${id}`, { waitUntil: "networkidle" });
    },
  },
  {
    name: "10-viewer-outline",
    user: "orlov",
    run: async (page) => {
      const id = await documentIdByTitle(
        page,
        ORG,
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
      const id = await documentIdByTitle(page, ORG, "Договор поручения");
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
        ORG,
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

export const USERS = {
  orlov: "orlov@polyarnaya-zvezda.example",
  belov: "belov@polyarnaya-zvezda.example",
  lebedev: "lebedev@rechnoy-port.example",
  sokolova: "sokolova@sokolova.example",
};
