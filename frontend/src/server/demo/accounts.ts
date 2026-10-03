import "server-only";

import { readFile } from "node:fs/promises";

import { parse } from "yaml";
import { z } from "zod";

import { serverConfig } from "../config";

export const DEMO_ROLES = ["owner", "lawyer", "observer", "operator"] as const;
export type DemoRole = (typeof DEMO_ROLES)[number];

export interface DemoAccount {
  role: DemoRole;
  email: string;
  password: string;
  name: string;
  /** The organization the account works in; none for the platform operator. */
  organization: string | null;
}

const person = z.object({
  email: z.string(),
  first_name: z.string(),
  last_name: z.string(),
  password: z.string(),
});
const seedSchema = z.object({
  demo_login: z.record(z.string(), z.string()),
  platform_admin: person,
  organizations: z.array(z.object({ name: z.string(), members: z.array(person) })),
});

/**
 * The accounts one-click sign-in opens, from the stand's seed file. Only a
 * demo stand reads it; elsewhere there are none.
 */
export async function demoAccounts(): Promise<DemoAccount[]> {
  const config = serverConfig();
  if (!config.SNOSKA_DEMO_MODE) return [];
  const seed = seedSchema.parse(parse(await readFile(config.SNOSKA_DEMO_SEED, "utf8")));
  return DEMO_ROLES.flatMap((role) => {
    const email = seed.demo_login[role];
    if (!email) return [];
    if (seed.platform_admin.email === email) {
      const admin = seed.platform_admin;
      return [account(role, admin, null)];
    }
    for (const organization of seed.organizations) {
      const member = organization.members.find((item) => item.email === email);
      if (member) return [account(role, member, organization.name)];
    }
    return [];
  });
}

function account(
  role: DemoRole,
  entry: z.infer<typeof person>,
  organization: string | null,
): DemoAccount {
  return {
    role,
    email: entry.email,
    password: entry.password,
    name: `${entry.first_name} ${entry.last_name}`,
    organization,
  };
}
