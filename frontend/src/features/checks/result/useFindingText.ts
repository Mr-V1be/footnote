"use client";

import { useTranslations } from "next-intl";
import { useCallback } from "react";

import type { Finding } from "@/shared/api/types";
import type { Messages } from "@/shared/i18n/messages";

type Detail = Finding["detail"];
type DetailCode = keyof Messages["checks"]["detail"];
type RequisiteCode = keyof Messages["requisites"];

/**
 * What is wrong, in words. Rules send a message code with parameters, which
 * the interface translates; a model's explanation arrives written.
 * Codes come from the server's rules and may be newer than the catalogue:
 * an unknown one is shown as it is.
 */
export function useFindingText(): (detail: Detail) => string {
  const t = useTranslations("checks.detail");
  const requisites = useTranslations("requisites");
  return useCallback(
    (detail: Detail) => {
      if (detail.text) return detail.text;
      const code = (detail.code ?? "") as DetailCode;
      if (!t.has(code)) return detail.code ?? "";
      const params = { ...detail.params };
      const requisite = params.requisite as RequisiteCode | undefined;
      if (typeof requisite === "string") {
        params.requisite = requisites.has(requisite) ? requisites(requisite) : requisite;
      }
      return t(code, params);
    },
    [t, requisites],
  );
}
