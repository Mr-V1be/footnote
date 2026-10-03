"use client";

import { IconBuildingSkyscraper, IconHeartbeat, IconReceipt, type Icon } from "@tabler/icons-react";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { SessionProvider } from "@/features/session/session";
import { AppFrame } from "@/features/shell/AppFrame";
import { ContextSwitcher } from "@/features/shell/ContextSwitcher";
import { Sidebar } from "@/features/shell/Sidebar";
import type { Me, Permission } from "@/shared/api/types";
import type { Messages } from "@/shared/i18n/messages";

interface PlatformSection {
  id: string;
  icon: Icon;
  label: keyof Messages["platform"]["nav"];
  permission: Permission;
}

/** Sections of the platform console. A new section is a new entry here. */
const PLATFORM_SECTIONS: readonly PlatformSection[] = [
  {
    id: "organizations",
    icon: IconBuildingSkyscraper,
    label: "organizations",
    permission: "platform.tenants.read",
  },
  { id: "plans", icon: IconReceipt, label: "plans", permission: "platform.tenants.read" },
  { id: "system", icon: IconHeartbeat, label: "system", permission: "platform.system.read" },
];

function PlatformSidebar({ me, onNavigate }: { me: Me; onNavigate?: () => void }) {
  const t = useTranslations("platform");
  const pathname = usePathname();
  const links = PLATFORM_SECTIONS.filter((section) =>
    me.platformPermissions.includes(section.permission),
  ).map((section) => ({
    id: section.id,
    icon: section.icon,
    label: t(`nav.${section.label}`),
    href: `/platform/${section.id}`,
    active: pathname.startsWith(`/platform/${section.id}`),
  }));
  return (
    <Sidebar
      context={<ContextSwitcher current={{ kind: "platform" }} name={t("title")} />}
      groups={[{ id: "platform", links }]}
      subtitle={t("operator")}
      onNavigate={onNavigate}
    />
  );
}

/** Pages of the platform's operator: organizations, plans, the system. */
export function PlatformShell({ me, children }: { me: Me; children: ReactNode }) {
  return (
    <SessionProvider me={me}>
      <AppFrame sidebar={(onNavigate) => <PlatformSidebar me={me} onNavigate={onNavigate} />}>
        {children}
      </AppFrame>
    </SessionProvider>
  );
}
