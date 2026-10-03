"use client";

import { IconDatabaseOff, IconPlugConnectedX, IconTool } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { useOrganizationCan } from "@/features/session/membership";
import { Notice } from "@/shared/ui/notice/Notice";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import styles from "./ask.module.css";

/** What the administrator does, in order: settings of the model APIs, then the index. */
const MODEL_STEPS = ["llm", "embedding", "index", "restart"] as const;
const INDEX_STEPS = ["index"] as const;

/**
 * Why questions cannot be answered now: no model API, or the norm is not
 * indexed yet. The owner also sees what the stand's administrator has to do.
 */
export function AskUnavailable({ reason }: { reason: "model" | "index" }) {
  const t = useTranslations("ask.unavailable");
  const owner = useOrganizationCan("members.manage");
  const steps = reason === "model" ? MODEL_STEPS : INDEX_STEPS;
  return (
    <div className={styles.unavailable}>
      <StatePanel
        icon={
          reason === "model" ? (
            <IconPlugConnectedX stroke={1.75} />
          ) : (
            <IconDatabaseOff stroke={1.75} />
          )
        }
        role="status"
        title={reason === "model" ? t("modelTitle") : t("indexTitle")}
        description={reason === "model" ? t("modelDescription") : t("indexDescription")}
      />
      {owner ? (
        <Notice icon={<IconTool stroke={1.75} />} title={t("forAdmin")}>
          <ol className={styles.steps}>
            {steps.map((step) => (
              <li key={step}>
                <code>{t(`steps.${step}`)}</code>
              </li>
            ))}
          </ol>
        </Notice>
      ) : null}
    </div>
  );
}
