import { useTranslations } from "next-intl";

import styles from "./brand.module.css";

/** The wordmark: the product name carries its own footnote marker. */
export function Brand({ compact = false }: { compact?: boolean }) {
  const t = useTranslations("app");
  return (
    <span className={styles.brand} aria-label={t("name")}>
      <span aria-hidden className={styles.word}>
        {compact ? t("name").slice(0, 1) : t("name")}
      </span>
      <sup aria-hidden className={styles.mark}>
        1
      </sup>
    </span>
  );
}
