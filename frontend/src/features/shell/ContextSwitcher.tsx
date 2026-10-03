"use client";

import { IconBuilding, IconCheck, IconSelector, IconServer2 } from "@tabler/icons-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { useIsOperator, useSession } from "@/features/session/session";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import {
  Menu,
  MenuContent,
  MenuItem,
  MenuLabel,
  MenuSeparator,
  MenuTrigger,
} from "@/shared/ui/menu/Menu";

import styles from "./context-switcher.module.css";

export type AppContext = { kind: "organization"; id: string } | { kind: "platform" };

/** Where the person works now: one of their organizations or the platform console. */
export function ContextSwitcher({
  current,
  name,
  subtitle,
}: {
  current: AppContext;
  name: string;
  subtitle?: string;
}) {
  const t = useTranslations();
  const roleLabel = useCodeLabel("roles");
  const me = useSession();
  const operator = useIsOperator();
  const Glyph = current.kind === "platform" ? IconServer2 : IconBuilding;
  return (
    <Menu>
      <MenuTrigger className={styles.trigger} aria-label={t("nav.switchOrganization")}>
        <span className={styles.logo} aria-hidden>
          <Glyph stroke={1.75} />
        </span>
        <span className={styles.text}>
          <span className={styles.name}>{name}</span>
          {subtitle ? <span className={styles.workspace}>{subtitle}</span> : null}
        </span>
        <IconSelector className={styles.chevron} stroke={1.75} aria-hidden />
      </MenuTrigger>
      <MenuContent>
        {me.memberships.length > 0 ? <MenuLabel>{t("nav.organization")}</MenuLabel> : null}
        {me.memberships.map((item) => (
          <MenuItem key={item.organization.id} asChild>
            <Link href={`/o/${item.organization.alias}`} className={styles.option}>
              <span className={styles.check}>
                {current.kind === "organization" && item.organization.id === current.id ? (
                  <IconCheck stroke={1.75} />
                ) : null}
              </span>
              <span className={styles.optionText}>
                <span className={styles.name}>{item.organization.name}</span>
                <span className={styles.workspace}>{roleLabel(item.role)}</span>
              </span>
            </Link>
          </MenuItem>
        ))}
        {operator ? (
          <>
            {me.memberships.length > 0 ? <MenuSeparator /> : null}
            <MenuItem asChild>
              <Link href="/platform" className={styles.option}>
                <span className={styles.check}>
                  {current.kind === "platform" ? <IconCheck stroke={1.75} /> : null}
                </span>
                <span className={styles.optionText}>
                  <span className={styles.name}>{t("platform.title")}</span>
                </span>
              </Link>
            </MenuItem>
          </>
        ) : null}
      </MenuContent>
    </Menu>
  );
}
