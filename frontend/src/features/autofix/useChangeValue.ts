"use client";

import { useTranslations } from "next-intl";
import { useCallback } from "react";

import type { VersionChange } from "@/shared/api/types";

/** A journal value with its units: "слева 15 мм", "12 пт", "1,25 см". */
export function useChangeValue(): (change: VersionChange, value: string) => string {
  const t = useTranslations("autofix.values");
  return useCallback(
    (change: VersionChange, value: string) => {
      const parts = value.split(/;|, /).filter(Boolean);
      switch (change.kind) {
        case "margins":
          return parts
            .map((part) => {
              const [side = "", size = ""] = part.split("=");
              return t("margin", { side, size });
            })
            .join(", ");
        case "font_size":
          return parts.map((size) => t("points", { size })).join(", ");
        case "line_spacing":
          return parts.map((size) => t("spacing", { size })).join(", ");
        case "first_line_indent":
          return parts.map((size) => t("centimetres", { size })).join(", ");
        case "text":
        case "format":
          return value;
      }
    },
    [t],
  );
}
