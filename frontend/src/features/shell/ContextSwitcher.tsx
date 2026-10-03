"use client";

import { IconBuilding, IconCheck, IconSelector } from "@tabler/icons-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { useMembership } from "@/features/session/membership";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuTrigger } from "@/shared/ui/menu/Menu";

import styles from "./organization-switcher.module.css";

export function OrganizationSwitcher() {
  const t = useTranslations();
  const roleLabel = useCodeLabel("roles");
  const { me, membership, workspaces } = useMembership();
  const current = membership.organization;
  const workspace = workspaces[0];
  return (
    <Menu>
      <MenuTrigger className={styles.trigger} aria-label={t("nav.switchOrganization")}>
        <span className={styles.logo} aria-hidden>
          <IconBuilding stroke={1.75} />
        </span>
        <span className={styles.text}>
          <span className={styles.name}>{current.name}</span>
          {workspace ? <span className={styles.workspace}>{workspace.name}</span> : null}
        </span>
        <IconSelector className={styles.chevron} stroke={1.75} aria-hidden />
      </MenuTrigger>
      <MenuContent>
        <MenuLabel>{t("nav.organization")}</MenuLabel>
        {me.memberships.map((item) => (
          <MenuItem key={item.organization.id} asChild>
            <Link href={`/o/${item.organization.alias}`} className={styles.option}>
              <span className={styles.check}>
                {item.organization.id === current.id ? <IconCheck stroke={1.75} /> : null}
              </span>
              <span className={styles.optionText}>
                <span className={styles.name}>{item.organization.name}</span>
                <span className={styles.workspace}>{roleLabel(item.role)}</span>
              </span>
            </Link>
          </MenuItem>
        ))}
      </MenuContent>
    </Menu>
  );
}
