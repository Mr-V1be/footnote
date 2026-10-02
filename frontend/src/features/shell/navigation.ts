import { IconChecklist, IconFiles, type Icon } from "@tabler/icons-react";

import type { Messages } from "@/shared/i18n/messages";

export interface NavContext {
  organization: string;
  workspace: string;
}

export interface NavSection {
  id: string;
  icon: Icon;
  label: keyof Messages["nav"];
  href: (context: NavContext) => string;
  /** Whether a pathname belongs to the section. */
  matches: (pathname: string, context: NavContext) => boolean;
}

/** Sections of the application. A new section is a new entry here. */
export const NAV_SECTIONS: readonly NavSection[] = [
  {
    id: "documents",
    icon: IconFiles,
    label: "documents",
    href: ({ organization, workspace }) => `/o/${organization}/w/${workspace}/documents`,
    matches: (pathname, { organization }) =>
      pathname.startsWith(`/o/${organization}/w/`) ||
      pathname.startsWith(`/o/${organization}/documents/`),
  },
  {
    id: "methodology",
    icon: IconChecklist,
    label: "methodology",
    href: ({ organization }) => `/o/${organization}/methodology`,
    matches: (pathname, { organization }) => pathname.startsWith(`/o/${organization}/methodology`),
  },
];
