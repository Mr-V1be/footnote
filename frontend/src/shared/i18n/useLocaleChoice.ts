"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { useCallback, useTransition } from "react";

import { LOCALE_COOKIE, LOCALE_COOKIE_MAX_AGE, type Locale } from "./locales";

/**
 * The interface language and a way to choose another. The choice is kept in
 * a cookie, so it wins over the browser's language from then on; the page
 * is rendered again in it, and data already loaded is read again, since the
 * server writes its texts (findings, citations) in the language asked for.
 */
export function useLocaleChoice(): {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  pending: boolean;
} {
  const locale = useLocale();
  const router = useRouter();
  const queries = useQueryClient();
  const [pending, startTransition] = useTransition();
  const setLocale = useCallback(
    (next: Locale) => {
      if (next === locale) return;
      document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=${LOCALE_COOKIE_MAX_AGE}; samesite=lax`;
      startTransition(() => {
        router.refresh();
        void queries.invalidateQueries();
      });
    },
    [locale, router, queries],
  );
  return { locale, setLocale, pending };
}
