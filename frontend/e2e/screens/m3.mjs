// Milestone 3: the service around the check — administration of an
// organization, integrations, plan and usage, automatic correction of
// formatting, questions to the corpus and the platform console.
//   MILESTONE=m3 node e2e/screenshots.mjs
import { BASE, documentIdByTitle } from "../runner.mjs";
import { answerWithSample } from "./ask-sample.mjs";

const OWNER = "polyarnaya-zvezda";
const ZARYA = "zarya";

async function open(page, path) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
}

const POLICY = "Политика обработки персональных данных";

async function openPolicy(page, query = "") {
  const id = await documentIdByTitle(page, ZARYA, POLICY);
  await open(page, `/o/${ZARYA}/documents/${id}${query}`);
}

export const SCREENS = [
  {
    name: "01-members",
    user: "owner",
    run: (page) => open(page, `/o/${OWNER}/settings/members`),
  },
  {
    name: "02-members-invite",
    user: "owner",
    run: async (page) => {
      await open(page, `/o/${OWNER}/settings/members`);
      await page.getByRole("button", { name: "Пригласить" }).first().click();
      await page.getByRole("dialog").waitFor();
    },
  },
  {
    name: "03-workspaces",
    user: "owner",
    run: (page) => open(page, `/o/${OWNER}/settings/workspaces`),
  },
  {
    name: "04-workspace",
    user: "owner",
    run: async (page) => {
      await open(page, `/o/${OWNER}/settings/workspaces`);
      await page.getByRole("link", { name: "Кадры" }).click();
      await page.waitForLoadState("networkidle");
    },
  },
  {
    name: "05-audit",
    user: "owner",
    run: (page) => open(page, `/o/${OWNER}/settings/audit`),
  },
  {
    name: "06-api-keys",
    user: "owner",
    run: (page) => open(page, `/o/${OWNER}/settings/api-keys`),
  },
  {
    // The token is shown once. The creation is answered in the browser, so
    // repeated captures do not leave revoked keys behind in the stand.
    name: "07-api-key-issued",
    user: "owner",
    run: async (page) => {
      await page.route("**/bff/api/v1/organizations/*/api-keys", async (route) => {
        if (route.request().method() !== "POST") return route.fallback();
        const body = route.request().postDataJSON();
        const token = `snk_${"x".repeat(6)}${Math.random().toString(36).slice(2, 12)}${"0".repeat(20)}`;
        await route.fulfill({
          status: 201,
          json: {
            key: {
              id: "00000000-0000-7000-8000-000000000001",
              name: body.name,
              prefix: token.slice(0, 10),
              scopes: body.scopes,
              createdBy: "Анна Ковалёва",
              createdAt: new Date().toISOString(),
              lastUsedAt: null,
              revokedAt: null,
            },
            token,
          },
        });
      });
      await open(page, `/o/${OWNER}/settings/api-keys`);
      await page.getByRole("button", { name: "Создать ключ" }).first().click();
      await page.getByLabel("Название").fill("Портал для партнёров");
      await page.getByRole("dialog").getByRole("button", { name: "Создать" }).click();
      await page.getByText("Ключ создан").waitFor();
    },
  },
  {
    name: "08-webhooks",
    user: "owner",
    run: (page) => open(page, `/o/${OWNER}/settings/webhooks`),
  },
  {
    name: "09-webhook-deliveries",
    user: "owner",
    run: async (page) => {
      await open(page, `/o/${OWNER}/settings/webhooks`);
      await page.getByRole("link", { name: "Демо-приёмник" }).click();
      await page.getByText("Доставки").first().waitFor();
      await page.waitForLoadState("networkidle");
    },
  },
  {
    name: "10-billing",
    user: "owner",
    run: (page) => open(page, `/o/${OWNER}/settings/billing`),
  },
  {
    name: "11-billing-plan-change",
    user: "owner",
    run: async (page) => {
      await open(page, `/o/${OWNER}/settings/billing`);
      await page.getByRole("button", { name: "Перейти", exact: true }).click();
      await page.getByRole("dialog").waitFor();
    },
  },
  {
    // The test provider's checkout, reached from the plan change (the open
    // invoice for a plan is reused, so repeated captures add nothing).
    name: "12-checkout",
    user: "zarya",
    run: async (page) => {
      await open(page, `/o/${ZARYA}/settings/billing`);
      const pay = page.getByRole("link", { name: "Оплатить" });
      if (await pay.count()) {
        await pay.first().click();
      } else {
        await page.getByRole("button", { name: "Перейти", exact: true }).first().click();
        await page.getByRole("dialog").getByRole("button", { name: "К оплате" }).click();
      }
      await page.waitForURL(/\/pay\/test\//);
      await page.waitForLoadState("networkidle");
    },
  },
  {
    // Paying returns to the plan page; the plan changes on the provider's
    // signed notification. Once paid, later captures show the result.
    name: "13-billing-paid",
    user: "zarya",
    run: async (page) => {
      await open(page, `/o/${ZARYA}/settings/billing`);
      const pay = page.getByRole("link", { name: "Оплатить" });
      if (await pay.count()) {
        await pay.first().click();
        await page.waitForURL(/\/pay\/test\//);
        await page.getByRole("button", { name: /^Оплатить/ }).click();
        await page.waitForURL(/payment=succeeded/);
      } else {
        await open(page, `/o/${ZARYA}/settings/billing?payment=succeeded`);
      }
      await page.getByText("Оплата подтверждена").waitFor({ timeout: 20_000 });
    },
  },
  {
    name: "14-autofix-preview",
    user: "lawyer",
    run: async (page) => {
      await openPolicy(page, "?v=1");
      await page.getByRole("button", { name: "Исправить оформление" }).click();
      await page.getByRole("dialog").getByText("Исправим").waitFor();
    },
  },
  {
    // The correction is made once; later captures open the version it made.
    name: "15-autofix-compare",
    user: "lawyer",
    run: async (page) => {
      await openPolicy(page);
      if (!(await page.getByText(/Оформление исправлено автоматически/).count())) {
        await open(page, `${new URL(page.url()).pathname}?v=1`);
        await page.getByRole("button", { name: "Исправить оформление" }).click();
        await page.getByRole("button", { name: "Создать исправленную версию" }).click();
        await page.waitForURL(/v=2/);
      }
      await page
        .getByText(/Проверено|замечани/)
        .first()
        .waitFor({ timeout: 60_000 });
      await page.getByRole("button", { name: /Было и стало/ }).click();
      await page.getByRole("dialog").waitFor();
    },
  },
  {
    // Without a model API key: the honest state, with steps for the administrator.
    name: "16-ask-model-missing",
    user: "owner",
    run: (page) => open(page, `/o/${OWNER}/ask`),
  },
  {
    name: "17-ask-answer",
    user: "owner",
    run: async (page) => {
      const id = await answerWithSample(page);
      await open(page, `/o/${OWNER}/ask/${id}`);
      await page.getByText("В норме не найдено").waitFor();
      await page.evaluate(() => window.scrollTo(0, 0));
    },
  },
  {
    name: "18-platform-organizations",
    user: "operator",
    run: (page) => open(page, "/platform/organizations"),
  },
  {
    name: "19-platform-plans",
    user: "operator",
    run: (page) => open(page, "/platform/plans"),
  },
  {
    name: "20-platform-system",
    user: "operator",
    run: (page) => open(page, "/platform/system"),
  },
  {
    // A workspace role: Igor observes the organization but is a lawyer in "Кадры".
    name: "21-workspace-documents",
    user: "workspaceLawyer",
    run: (page) => open(page, `/o/${OWNER}/w/kadry/documents`),
  },
];

export const USERS = {
  owner: "kovaleva@polyarnaya-zvezda.example",
  zarya: "ershov@zarya.example",
  lawyer: "polyakova@zarya.example",
  workspaceLawyer: "belov@polyarnaya-zvezda.example",
  operator: "operator@snoska.example",
};
