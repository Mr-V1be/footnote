"use client";

import { IconAlertTriangle, IconLock, IconMoodEmpty } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button/Button";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

/**
 * A screen or a block that did not load: no access, gone, or a failure that
 * a retry may fix — each with what to do next.
 */
export function LoadFailure({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const t = useTranslations("loadFailure");
  if (error instanceof ApiError && error.isForbidden) {
    return (
      <StatePanel
        icon={<IconLock stroke={1.75} />}
        role="alert"
        title={t("forbiddenTitle")}
        description={t("forbiddenDescription")}
      />
    );
  }
  if (error instanceof ApiError && error.isNotFound) {
    return (
      <StatePanel
        icon={<IconMoodEmpty stroke={1.75} />}
        role="alert"
        title={t("notFoundTitle")}
        description={t("notFoundDescription")}
      />
    );
  }
  return (
    <StatePanel
      icon={<IconAlertTriangle stroke={1.75} />}
      tone="critical"
      role="alert"
      title={t("errorTitle")}
      description={t("errorDescription")}
      action={
        <Button variant="secondary" onClick={onRetry}>
          {t("retry")}
        </Button>
      }
    />
  );
}
