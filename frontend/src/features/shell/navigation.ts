import {
  IconChecklist,
  IconFiles,
  IconFolders,
  IconHistory,
  IconKey,
  IconMessageQuestion,
  IconReceipt,
  IconUsers,
  IconWebhook,
  type Icon,
} from "@tabler/icons-react";

import type { Permission } from "@/shared/api/types";
import type { Messages } from "@/shared/i18n/messages";

export interface NavContext {
  organization: string;
  workspace: string;
}

export type NavGroupId = "work" | "organization";

export interface NavSection {
  id: string;
  icon: Icon;
  label: keyof Messages["nav"];
  group: NavGroupId;
  /** Shown only to those who hold it; the server refuses the rest anyway. */
  permission?: Permission;
  href: (context: NavContext) => string;
  /** Whether a pathname belongs to the section. */
  matches: (pathname: string, context: NavContext) => boolean;
}

/** Groups in the order of the sidebar; a group without a label leads it. */
export const NAV_GROUPS: readonly { id: NavGroupId; label?: keyof Messages["nav"] }[] = [
  { id: "work" },
  { id: "organization", label: "organizationGroup" },
];

function settings(
  id: string,
  icon: Icon,
  label: keyof Messages["nav"],
  permission: Permission,
): NavSection {
  return {
    id,
    icon,
    label,
    group: "organization",
    permission,
    href: ({ organization }) => `/o/${organization}/settings/${id}`,
    matches: (pathname, { organization }) =>
      pathname.startsWith(`/o/${organization}/settings/${id}`),
  };
}

/** Sections of an organization. A new section is a new entry here. */
export const NAV_SECTIONS: readonly NavSection[] = [
  {
    id: "documents",
    icon: IconFiles,
    label: "documents",
    group: "work",
    permission: "documents.read",
    href: ({ organization, workspace }) => `/o/${organization}/w/${workspace}/documents`,
    matches: (pathname, { organization }) =>
      pathname.startsWith(`/o/${organization}/w/`) ||
      pathname.startsWith(`/o/${organization}/documents/`),
  },
  {
    id: "ask",
    icon: IconMessageQuestion,
    label: "ask",
    group: "work",
    permission: "norms.ask",
    href: ({ organization }) => `/o/${organization}/ask`,
    matches: (pathname, { organization }) => pathname.startsWith(`/o/${organization}/ask`),
  },
  {
    id: "methodology",
    icon: IconChecklist,
    label: "methodology",
    group: "work",
    href: ({ organization }) => `/o/${organization}/methodology`,
    matches: (pathname, { organization }) => pathname.startsWith(`/o/${organization}/methodology`),
  },
  settings("members", IconUsers, "members", "members.manage"),
  settings("workspaces", IconFolders, "workspaces", "workspaces.manage"),
  settings("api-keys", IconKey, "apiKeys", "integrations.manage"),
  settings("webhooks", IconWebhook, "webhooks", "integrations.manage"),
  settings("audit", IconHistory, "audit", "audit.read"),
  settings("billing", IconReceipt, "billing", "billing.read"),
];
