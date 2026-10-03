"use client";

import { IconArrowsDiff, IconFocus2, IconWand } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { useApi } from "@/shared/api/ApiProvider";
import type { CheckDefinition, VersionChange } from "@/shared/api/types";
import { useMediaQuery } from "@/shared/hooks/useMediaQuery";
import { Button } from "@/shared/ui/button/Button";
import { Drawer, DrawerContent } from "@/shared/ui/drawer/Drawer";
import { Notice } from "@/shared/ui/notice/Notice";
import { Skeleton } from "@/shared/ui/skeleton/Skeleton";

import styles from "./autofix.module.css";
import { autofixKeys, fetchChanges } from "./queries";
import { useChangeValue } from "./useChangeValue";

/**
 * A version made by an automatic correction: where it came from and, on
 * request, every corrected place as before and after.
 */
export function VersionChanges({
  organization,
  documentId,
  version,
  source,
  checks,
  onLocate,
}: {
  organization: string;
  documentId: string;
  version: number;
  /** The version the correction was made from. */
  source: number | null;
  checks: readonly CheckDefinition[];
  /** Shows a block of this version's text. */
  onLocate: (blockOrdinal: number) => void;
}) {
  const t = useTranslations("autofix");
  const tc = useTranslations("common");
  const api = useApi();
  const wide = useMediaQuery("(width >= 48rem)");
  const [open, setOpen] = useState(false);
  const changes = useQuery({
    queryKey: autofixKeys.changes(organization, documentId, version),
    queryFn: () => fetchChanges(api, organization, documentId, version),
    staleTime: Infinity,
  });
  const titles = new Map(checks.map((check) => [check.code, check.title]));
  const count = changes.data?.length;
  return (
    <>
      <Notice
        icon={<IconWand stroke={1.75} />}
        tone="ink"
        title={t("origin", { source: source ?? 1 })}
        action={
          <Button
            variant="secondary"
            size="sm"
            icon={<IconArrowsDiff stroke={1.75} />}
            onClick={() => setOpen(true)}
            disabled={!count}
          >
            {count === undefined ? t("compare") : t("compareCount", { count })}
          </Button>
        }
      />
      <Drawer open={open} onOpenChange={setOpen}>
        <DrawerContent
          side={wide ? "right" : "bottom"}
          title={t("compareTitle")}
          closeLabel={tc("close")}
        >
          {changes.data ? (
            <ol className={styles.changes}>
              {changes.data.map((change, index) => (
                <ChangeItem
                  key={`${change.checkCode}-${index}`}
                  change={change}
                  title={titles.get(change.checkCode) ?? change.checkCode}
                  onLocate={
                    change.blockOrdinal === null
                      ? undefined
                      : () => {
                          setOpen(false);
                          const ordinal = change.blockOrdinal ?? 0;
                          window.requestAnimationFrame(() => onLocate(ordinal));
                        }
                  }
                />
              ))}
            </ol>
          ) : (
            <Skeleton shape="block" height="10rem" />
          )}
        </DrawerContent>
      </Drawer>
    </>
  );
}

function ChangeItem({
  change,
  title,
  onLocate,
}: {
  change: VersionChange;
  title: string;
  onLocate?: () => void;
}) {
  const t = useTranslations("autofix");
  const value = useChangeValue();
  return (
    <li className={styles.change}>
      <div className={styles.changeHead}>
        <span className={styles.changeTitle}>{title}</span>
        {change.kind !== "text" && change.kind !== "margins" ? (
          <span className={styles.changePlaces}>{t("paragraphs", { count: change.places })}</span>
        ) : null}
      </div>
      <dl className={styles.diff}>
        <div className={styles.before}>
          <dt>{t("before")}</dt>
          <dd>{value(change, change.before)}</dd>
        </div>
        <div className={styles.after}>
          <dt>{t("after")}</dt>
          <dd>{value(change, change.after)}</dd>
        </div>
      </dl>
      {onLocate ? (
        <Button variant="ghost" size="sm" icon={<IconFocus2 stroke={1.75} />} onClick={onLocate}>
          {t("showInText")}
        </Button>
      ) : null}
    </li>
  );
}
