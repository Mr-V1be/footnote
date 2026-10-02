"use client";

import { useTranslations } from "next-intl";

import { Tooltip } from "@/shared/ui/tooltip/Tooltip";

import styles from "./demo-mark.module.css";

/** A quiet reminder that the stand holds fictional data. */
export function DemoMark() {
  const t = useTranslations("app");
  return (
    <Tooltip content={t("demoHint")}>
      <span className={styles.mark} tabIndex={0}>
        {t("demo")}
      </span>
    </Tooltip>
  );
}
