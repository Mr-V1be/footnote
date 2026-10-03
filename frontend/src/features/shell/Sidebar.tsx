"use client";

import type { Icon } from "@tabler/icons-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Brand } from "./Brand";
import { DemoMark } from "./DemoMark";
import styles from "./sidebar.module.css";
import { UserMenu } from "./UserMenu";

export interface SidebarLink {
  id: string;
  icon: Icon;
  label: string;
  href: string;
  active: boolean;
}

export interface SidebarGroup {
  id: string;
  label?: string;
  links: readonly SidebarLink[];
}

/**
 * The column of an area of the application: the wordmark, where the person
 * is (an organization, the platform), the sections and the person's menu.
 */
export function Sidebar({
  context,
  groups,
  subtitle,
  onNavigate,
}: {
  context: ReactNode;
  groups: readonly SidebarGroup[];
  /** Under the person's name: their role here. */
  subtitle: string;
  onNavigate?: () => void;
}) {
  const t = useTranslations("nav");
  return (
    <div className={styles.sidebar}>
      <div className={styles.brand}>
        <Brand />
        <DemoMark />
      </div>
      {context}
      <nav aria-label={t("label")} className={styles.nav}>
        {groups
          .filter((group) => group.links.length > 0)
          .map((group) => (
            <div key={group.id} className={styles.group}>
              {group.label ? <p className={styles.groupLabel}>{group.label}</p> : null}
              <ul>
                {group.links.map((link) => {
                  const Glyph = link.icon;
                  return (
                    <li key={link.id}>
                      <Link
                        href={link.href}
                        className={`${styles.link} ${link.active ? styles.active : ""}`}
                        aria-current={link.active ? "page" : undefined}
                        onClick={onNavigate}
                      >
                        <Glyph stroke={1.75} aria-hidden />
                        <span>{link.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
      </nav>
      <div className={styles.footer}>
        <UserMenu subtitle={subtitle} />
      </div>
    </div>
  );
}
