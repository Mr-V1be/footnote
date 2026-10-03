"use client";

import { IconCpu } from "@tabler/icons-react";
import { useFormatter, useTranslations } from "next-intl";

import type { ModelTrial } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge/Badge";
import { DataList, DataRow } from "@/shared/ui/data-list/DataList";
import { Section } from "@/shared/ui/section/Section";

import { useQualityFormat } from "./useQualityFormat";

/** Candidate models measured on the same documents, and the one chosen. */
export function ModelTrials({
  trials,
  chosen,
}: {
  trials: readonly ModelTrial[];
  chosen: string | null;
}) {
  const t = useTranslations("methodology");
  const format = useFormatter();
  const { seconds } = useQualityFormat();
  const share = (value: number | null) =>
    value === null ? t("noCases") : format.number(value, { style: "percent" });
  const measured = trials.filter((trial) => trial.precision !== null || trial.recall !== null);
  const documents = measured[0]?.documents ?? null;
  return (
    <Section
      title={t("trials")}
      meta={documents === null ? null : t("trialsDocuments", { count: documents })}
    >
      <DataList label={t("trials")}>
        {trials.map((trial) => {
          const ran = trial.precision !== null || trial.recall !== null;
          return (
            <DataRow
              key={trial.model}
              leading={<IconCpu stroke={1.75} />}
              title={trial.model}
              description={
                <>
                  {trial.model === chosen ? <Badge tone="success">{t("chosen")}</Badge> : null}
                  {ran ? (
                    <span>
                      {t("trialTime", {
                        time:
                          trial.modelMsPerDocument === null
                            ? "—"
                            : seconds(trial.modelMsPerDocument),
                      })}
                    </span>
                  ) : (
                    <span>{t("trialUnavailable")}</span>
                  )}
                </>
              }
              aside={
                ran ? (
                  <>
                    <span>{t("trialPrecision", { value: share(trial.precision) })}</span>
                    <span>{t("trialRecall", { value: share(trial.recall) })}</span>
                  </>
                ) : (
                  <Badge>{t("notMeasured")}</Badge>
                )
              }
            />
          );
        })}
      </DataList>
    </Section>
  );
}
