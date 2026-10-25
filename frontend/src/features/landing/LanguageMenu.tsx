"use client";

import { IconLanguage } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { isLocale, LOCALE_NAMES, LOCALES } from "@/shared/i18n/locales";
import { useLocaleChoice } from "@/shared/i18n/useLocaleChoice";
import { Button } from "@/shared/ui/button/Button";
import {
  Menu,
  MenuContent,
  MenuRadioGroup,
  MenuRadioItem,
  MenuTrigger,
} from "@/shared/ui/menu/Menu";

import styles from "./landing.module.css";

/** The interface language for a guest, shown by its code beside the icon. */
export function LanguageMenu() {
  const t = useTranslations("user");
  const { locale, setLocale, pending } = useLocaleChoice();
  return (
    <Menu>
      <MenuTrigger asChild>
        <Button
          variant="ghost"
          icon={<IconLanguage stroke={1.75} />}
          aria-label={t("languageOf", { language: LOCALE_NAMES[locale] })}
          aria-busy={pending || undefined}
          className={styles.language}
        >
          {locale.toUpperCase()}
        </Button>
      </MenuTrigger>
      <MenuContent align="end">
        <MenuRadioGroup
          value={locale}
          onValueChange={(value) => {
            if (isLocale(value)) setLocale(value);
          }}
        >
          {LOCALES.map((option) => (
            <MenuRadioItem key={option} value={option} lang={option}>
              {LOCALE_NAMES[option]}
            </MenuRadioItem>
          ))}
        </MenuRadioGroup>
      </MenuContent>
    </Menu>
  );
}
