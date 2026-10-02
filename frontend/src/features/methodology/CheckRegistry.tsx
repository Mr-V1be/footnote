"use client";

import { IconFileDescription, IconRuler2, IconScale } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import type { CheckCatalog, DocumentKind, Quality } from "@/shared/api/types";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { Typeset } from "@/shared/typography/Typeset";
import { Badge } from "@/shared/ui/badge/Badge";
import { Select } from "@/shared/ui/select/Select";

import styles from "./methodology.module.css";
import { ShareValue } from "./ShareValue";
import { isMeasured, useQualityFormat, type Share } from "./useQualityFormat";

const ALL_KINDS = "__all";
const METHOD_ICONS = { deterministic: IconRuler2, model: IconScale } as const;
const SHARES: readonly Share[] = ["precision", "recall"];

/** Every check the product runs, by family, with what it requires and cites. */
export function CheckRegistry({
  catalog,
  quality,
  kinds,
}: {
  catalog: CheckCatalog;
  quality: Quality | null;
  kinds: readonly DocumentKind[];
}) {
  const t = useTranslations("methodology");
  const tc = useTranslations("checks");
  const familyLabel = useCodeLabel("families");
  const kindLabel = useCodeLabel("kinds");
  const { share } = useQualityFormat();
  const [kind, setKind] = useState(ALL_KINDS);
  const byCheck = new Map(quality?.checks.map((group) => [group.code, group.metrics]));
  const visible = catalog.checks.filter(
    (check) => kind === ALL_KINDS || check.kinds.includes(kind),
  );
  const families = [...catalog.families]
    .sort((a, b) => a.rank - b.rank)
    .map((family) => ({
      family,
      checks: visible.filter((check) => check.family === family.code),
    }))
    .filter((group) => group.checks.length > 0);

  return (
    <section className={styles.section} aria-labelledby="checks-heading">
      <div className={styles.sectionHead}>
        <h2 id="checks-heading" className={styles.sectionTitle}>
          {t("checks")}
        </h2>
        <Select
          size="sm"
          value={kind}
          onValueChange={setKind}
          label={t("kindFilter")}
          icon={<IconFileDescription stroke={1.75} />}
          options={[
            { value: ALL_KINDS, label: t("allKinds") },
            ...kinds.map((item) => ({ value: item.code, label: kindLabel(item.code) })),
          ]}
        />
      </div>
      {families.map(({ family, checks }) => (
        <div key={family.code} className={styles.family}>
          <h3 className={styles.familyTitle}>
            <span>
              <Typeset text={familyLabel(family.code)} />
            </span>
            <span className={styles.familyCount}>{t("checksCount", { count: checks.length })}</span>
          </h3>
          <ul className={styles.checks}>
            {checks.map((check) => {
              const MethodIcon = METHOD_ICONS[check.method];
              const metrics = byCheck.get(check.code);
              return (
                <li key={check.code} className={styles.check}>
                  <div className={styles.checkMain}>
                    <p className={styles.checkTitle}>
                      <Typeset text={check.title} />
                    </p>
                    <p className={styles.checkRequirement}>
                      <Typeset text={check.requirement} />
                    </p>
                  </div>
                  <div className={styles.checkNorm}>
                    <span className={styles.checkLabel}>{t("norm")}</span>
                    <ul className={styles.citations}>
                      {check.citations.map((citation) => (
                        <li key={citation}>
                          <Typeset text={citation} />
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className={styles.checkTags}>
                    <Badge tone={check.severity}>{tc(`severity.${check.severity}`)}</Badge>
                    <span className={styles.method}>
                      <MethodIcon stroke={1.75} aria-hidden />
                      {t(`methodShort.${check.method}`)}
                    </span>
                  </div>
                  {quality ? (
                    <div className={styles.checkShares}>
                      {isMeasured(metrics) ? (
                        <dl className={styles.shareList}>
                          {SHARES.map((which) => (
                            <div key={which}>
                              <dt className={styles.checkShareLabel}>{t(which)}</dt>
                              <dd className={styles.checkShareValue}>
                                <ShareValue text={share(metrics, which)} />
                              </dd>
                            </div>
                          ))}
                        </dl>
                      ) : (
                        // Neither share has a number: one figure says why.
                        <ShareValue text={share(metrics, "precision")} />
                      )}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </section>
  );
}
