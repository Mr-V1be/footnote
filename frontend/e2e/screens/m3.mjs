// Milestone 3: the service around the check — administration of an
// organization, integrations, plan and usage, automatic correction of
// formatting, questions to the corpus and the platform console.
//   MILESTONE=m3 node e2e/screenshots.mjs
import { BASE } from "../runner.mjs";

const OWNER = "polyarnaya-zvezda";

async function open(page, path) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
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
];

export const USERS = {
  owner: "kovaleva@polyarnaya-zvezda.example",
  operator: "operator@snoska.example",
};
