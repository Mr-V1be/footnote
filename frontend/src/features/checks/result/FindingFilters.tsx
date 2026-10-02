"use client";

import { IconAdjustmentsHorizontal, IconChevronDown } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import type { Severity } from "@/shared/api/types";
import { Button } from "@/shared/ui/button/Button";
import { Menu, MenuCheckboxItem, MenuContent, MenuTrigger } from "@/shared/ui/menu/Menu";
import { Select } from "@/shared/ui/select/Select";

import {
  REVIEW_SCOPES,
  SEVERITIES,
  type FindingFilters as Filters,
  type ReviewScope,
} from "../findings";
import styles from "./result.module.css";

/** Which findings are shown: severities (several at once) and what was decided. */
export function FindingFilters({
  filters,
  counts,
  onChange,
}: {
  filters: Filters;
  counts: Record<Severity, number>;
  onChange: (filters: Filters) => void;
}) {
  const t = useTranslations("checks");
  const all = filters.severities.length === SEVERITIES.length;
  const toggle = (severity: Severity, checked: boolean) => {
    const next = checked
      ? SEVERITIES.filter((item) => item === severity || filters.severities.includes(item))
      : filters.severities.filter((item) => item !== severity);
    // Hiding every severity shows nothing at all; keep at least one.
    if (next.length > 0) onChange({ ...filters, severities: next });
  };
  return (
    <div className={styles.filters}>
      <Menu>
        <MenuTrigger asChild>
          <Button
            variant="secondary"
            size="sm"
            icon={<IconAdjustmentsHorizontal stroke={1.75} />}
            aria-label={t("filterSeverity")}
          >
            {all ? t("allSeverities") : t("someSeverities", { count: filters.severities.length })}
            <IconChevronDown stroke={1.75} className={styles.chevron} aria-hidden />
          </Button>
        </MenuTrigger>
        <MenuContent align="start">
          {SEVERITIES.map((severity) => (
            <MenuCheckboxItem
              key={severity}
              checked={filters.severities.includes(severity)}
              onCheckedChange={(checked) => toggle(severity, checked)}
            >
              <span className={styles.menuSeverity} data-severity={severity}>
                {t(`severity.${severity}`)}
              </span>
              <span className={styles.menuCount}>{counts[severity]}</span>
            </MenuCheckboxItem>
          ))}
        </MenuContent>
      </Menu>
      <Select
        label={t("filterScope")}
        size="sm"
        value={filters.scope}
        onValueChange={(value) => {
          const scope = REVIEW_SCOPES.find((item) => item === value);
          if (scope) onChange({ ...filters, scope: scope satisfies ReviewScope });
        }}
        options={REVIEW_SCOPES.map((scope) => ({ value: scope, label: t(`scope.${scope}`) }))}
      />
    </div>
  );
}
