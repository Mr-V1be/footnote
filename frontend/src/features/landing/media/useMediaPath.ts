"use client";

import { useLocale } from "next-intl";
import { useCallback } from "react";

import { useResolvedTheme } from "@/shared/theme/useResolvedTheme";

/**
 * Where the landing's recordings of the product live (see e2e/landing): a
 * set per interface language, each in both themes, so the product is shown
 * in the language and the theme the page is read in.
 */
const MEDIA_ROOT = "/landing";

export function useMediaPath(): (name: string, extension: "webp" | "mp4") => string {
  const locale = useLocale();
  const theme = useResolvedTheme();
  return useCallback(
    (name, extension) => `${MEDIA_ROOT}/${locale}/${name}-${theme}.${extension}`,
    [locale, theme],
  );
}
