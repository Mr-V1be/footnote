"use client";

import { useTranslations } from "next-intl";
import { useCallback } from "react";

import { ApiError } from "@/shared/api/errors";

import type { Messages } from "./messages";

/**
 * What went wrong, in words, for an error from the API: by its stable code
 * when the catalogue knows it, in general terms otherwise.
 */
export function useErrorText(): (error: unknown) => string {
  const t = useTranslations("problems");
  return useCallback(
    (error: unknown) => {
      if (error instanceof ApiError) {
        const key = error.code as keyof Messages["problems"];
        if (t.has(key)) return t(key);
      }
      return t("unexpected");
    },
    [t],
  );
}
