"use client";

import { IconAlertTriangle } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { Button } from "@/shared/ui/button/Button";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import styles from "./standalone.module.css";

export default function ErrorBoundary({ reset }: { error: Error; reset: () => void }) {
  const t = useTranslations();
  return (
    <div className={styles.screen}>
      <StatePanel
        icon={<IconAlertTriangle stroke={1.75} />}
        tone="critical"
        role="alert"
        title={t("errors.unexpectedTitle")}
        description={t("errors.unexpectedDescription")}
        action={
          <Button variant="primary" onClick={reset}>
            {t("common.retry")}
          </Button>
        }
      />
    </div>
  );
}
