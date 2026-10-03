"use client";

import { IconDeviceDesktop, IconMoon, IconSun } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { parseTheme, THEMES } from "@/shared/theme/theme";
import { useThemePreference } from "@/shared/theme/ThemeContext";
import { IconButton } from "@/shared/ui/icon-button/IconButton";
import {
  Menu,
  MenuContent,
  MenuRadioGroup,
  MenuRadioItem,
  MenuTrigger,
} from "@/shared/ui/menu/Menu";

const ICONS = { system: IconDeviceDesktop, light: IconSun, dark: IconMoon } as const;
const LABELS = { system: "themeSystem", light: "themeLight", dark: "themeDark" } as const;

/** The theme for a guest: as the system, light or dark. */
export function ThemeMenu() {
  const t = useTranslations("user");
  const { theme, setTheme } = useThemePreference();
  const Glyph = ICONS[theme];
  return (
    <Menu>
      <MenuTrigger asChild>
        <IconButton label={t("theme")} icon={<Glyph stroke={1.75} />} />
      </MenuTrigger>
      <MenuContent align="end">
        <MenuRadioGroup value={theme} onValueChange={(value) => setTheme(parseTheme(value))}>
          {THEMES.map((option) => (
            <MenuRadioItem key={option} value={option}>
              {t(LABELS[option])}
            </MenuRadioItem>
          ))}
        </MenuRadioGroup>
      </MenuContent>
    </Menu>
  );
}
