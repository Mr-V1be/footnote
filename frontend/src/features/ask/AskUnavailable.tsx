"use client";

import { IconDatabaseOff, IconHourglass, IconPlugConnectedX, IconTool } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { useOrganizationCan } from "@/features/session/membership";
import { Notice } from "@/shared/ui/notice/Notice";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import styles from "./ask.module.css";

/** What the administrator does, in order: settings of the model APIs, then the index. */
const STEPS = {
  model: ["llm", "embedding", "index", "restart"],
  index: ["index"],
  limit: ["paid"],
} as const;

/**
 * Why questions cannot be answered now: no model API, or the norm is not
 * indexed yet. The owner also sees what the stand's administrator has to do.
 */
export type UnavailableReason = "model" | "index" | "limit";

const ICONS = { model: IconPlugConnectedX, index: IconDatabaseOff, limit: IconHourglass } as const;

export function AskUnavailable({ reason }: { reason: UnavailableReason }) {
  const t = useTranslations("ask.unavailable");
  const owner = useOrganizationCan("members.manage");
  const steps = STEPS[reason];
  const Glyph = ICONS[reason];
  return (
    <div className={styles.unavailable}>
      <StatePanel
        icon={<Glyph stroke={1.75} />}
        role="status"
        title={t(`${reason}Title`)}
        description={t(`${reason}Description`)}
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
