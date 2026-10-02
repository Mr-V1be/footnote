"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";

import { useMembership } from "@/features/session/membership";

import { Brand } from "./Brand";
import { DemoMark } from "./DemoMark";
import { NAV_SECTIONS } from "./navigation";
import { OrganizationSwitcher } from "./OrganizationSwitcher";
import styles from "./sidebar.module.css";
import { UserMenu } from "./UserMenu";

export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const { membership, workspaces } = useMembership();
  const workspace = workspaces[0]?.slug ?? "main";
  const context = { organization: membership.organization.alias, workspace };
  return (
    <div className={styles.sidebar}>
      <div className={styles.brand}>
        <Brand />
        <DemoMark />
      </div>
      <OrganizationSwitcher />
      <nav aria-label={t("label")} className={styles.nav}>
        <ul>
          {NAV_SECTIONS.map((section) => {
            const active = section.matches(pathname, context);
            const Icon = section.icon;
            return (
              <li key={section.id}>
                <Link
                  href={section.href(context)}
                  className={`${styles.link} ${active ? styles.active : ""}`}
                  aria-current={active ? "page" : undefined}
                  onClick={onNavigate}
                >
                  <Icon stroke={1.75} aria-hidden />
                  <span>{t(section.label)}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className={styles.footer}>
        <UserMenu />
      </div>
    </div>
  );
}
