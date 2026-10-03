"use client";

import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { MembershipProvider, type MembershipState } from "@/features/session/membership";
import { SessionProvider } from "@/features/session/session";
import type { Me } from "@/shared/api/types";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";

import { AppFrame } from "./AppFrame";
import { ContextSwitcher } from "./ContextSwitcher";
import { NAV_GROUPS, NAV_SECTIONS } from "./navigation";
import { Sidebar, type SidebarGroup } from "./Sidebar";

function OrganizationSidebar({
  state,
  onNavigate,
}: {
  state: MembershipState;
  onNavigate?: () => void;
}) {
  const t = useTranslations("nav");
  const roleLabel = useCodeLabel("roles");
  const pathname = usePathname();
  const { membership, workspaces } = state;
  const context = {
    organization: membership.organization.alias,
    workspace: workspaces[0]?.slug ?? "main",
  };
  const groups: SidebarGroup[] = NAV_GROUPS.map((group) => ({
    id: group.id,
    label: group.label ? t(group.label) : undefined,
    links: NAV_SECTIONS.filter(
      (section) =>
        section.group === group.id &&
        (!section.permission || membership.permissions.includes(section.permission)),
    ).map((section) => ({
      id: section.id,
      icon: section.icon,
      label: t(section.label),
      href: section.href(context),
      active: section.matches(pathname, context),
    })),
  }));
  return (
    <Sidebar
      context={
        <ContextSwitcher
          current={{ kind: "organization", id: membership.organization.id }}
          name={membership.organization.name}
          subtitle={workspaces.length === 1 ? workspaces[0]?.name : undefined}
        />
      }
      groups={groups}
      subtitle={roleLabel(membership.role)}
      onNavigate={onNavigate}
    />
  );
}

/** Pages of an organization: its sections by the person's permissions. */
export function OrganizationShell({
  me,
  state,
  children,
}: {
  me: Me;
  state: MembershipState;
  children: ReactNode;
}) {
  return (
    <SessionProvider me={me}>
      <MembershipProvider value={state}>
        <AppFrame
          sidebar={(onNavigate) => <OrganizationSidebar state={state} onNavigate={onNavigate} />}
        >
          {children}
        </AppFrame>
      </MembershipProvider>
    </SessionProvider>
  );
}
