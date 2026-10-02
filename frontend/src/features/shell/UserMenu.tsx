"use client";

import { IconLogout } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useRef } from "react";

import { useMembership } from "@/features/session/membership";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { parseTheme, THEMES } from "@/shared/theme/theme";
import { useThemePreference } from "@/shared/theme/ThemeContext";
import { Avatar } from "@/shared/ui/avatar/Avatar";
import {
  Menu,
  MenuContent,
  MenuItem,
  MenuLabel,
  MenuRadioGroup,
  MenuRadioItem,
  MenuSeparator,
  MenuTrigger,
} from "@/shared/ui/menu/Menu";

import styles from "./user-menu.module.css";

const THEME_LABELS = { system: "themeSystem", light: "themeLight", dark: "themeDark" } as const;

export function UserMenu({ compact = false }: { compact?: boolean }) {
  const t = useTranslations("user");
  const roleLabel = useCodeLabel("roles");
  const { me, membership } = useMembership();
  const { theme, setTheme } = useThemePreference();
  const logout = useRef<HTMLFormElement>(null);
  return (
    <>
      <form ref={logout} action="/auth/logout" method="post" hidden />
      <Menu>
        <MenuTrigger
          className={`${styles.trigger} ${compact ? styles.compact : ""}`}
          aria-label={t("menu")}
        >
          <Avatar name={me.displayName} />
          {compact ? null : (
            <span className={styles.text}>
              <span className={styles.name}>{me.displayName}</span>
              <span className={styles.role}>{roleLabel(membership.role)}</span>
            </span>
          )}
        </MenuTrigger>
        <MenuContent align={compact ? "end" : "start"} side={compact ? "bottom" : "top"}>
          <div className={styles.identity}>
            <span className={styles.name}>{me.displayName}</span>
            {me.email ? <span className={styles.email}>{me.email}</span> : null}
          </div>
          <MenuSeparator />
          <MenuLabel>{t("theme")}</MenuLabel>
          <MenuRadioGroup value={theme} onValueChange={(value) => setTheme(parseTheme(value))}>
            {THEMES.map((option) => (
              <MenuRadioItem key={option} value={option}>
                {t(THEME_LABELS[option])}
              </MenuRadioItem>
            ))}
          </MenuRadioGroup>
          <MenuSeparator />
          <MenuItem
            icon={<IconLogout stroke={1.75} />}
            onSelect={() => logout.current?.requestSubmit()}
          >
            {t("signOut")}
          </MenuItem>
        </MenuContent>
      </Menu>
    </>
  );
}
