"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback } from "react";

import { bytesParts } from "./bytes";

export function useFormatBytes(): (bytes: number) => string {
  const t = useTranslations("format");
  const locale = useLocale();
  return useCallback(
    (bytes: number) => {
      const { unit, value } = bytesParts(bytes, locale);
      return t(unit, { value });
    },
    [t, locale],
  );
}
