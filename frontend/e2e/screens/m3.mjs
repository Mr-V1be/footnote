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
];

export const USERS = {
  owner: "kovaleva@polyarnaya-zvezda.example",
  operator: "operator@snoska.example",
};
