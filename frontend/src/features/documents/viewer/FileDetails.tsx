"use client";

import { useFormatter, useTranslations } from "next-intl";

import type { DocumentStructure } from "@/shared/api/types";
import { useFormatBytes } from "@/shared/format/useFormatBytes";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { Facts } from "@/shared/ui/facts/Facts";

const PERCENT = 100;

export function FileDetails({ structure }: { structure: DocumentStructure }) {
  const t = useTranslations();
  const format = useFormatter();
  const formatBytes = useFormatBytes();
  const formatLabel = useCodeLabel("formats");
  const version = structure.version;
  const page = structure.layout[0];
  const rows: [string, string][] = [
    [t("viewer.file"), version.filename],
    [t("viewer.format"), formatLabel(version.format)],
    [t("viewer.size"), formatBytes(version.sizeBytes)],
  ];
  if (version.pageCount) rows.push([t("viewer.pagesLabel"), String(version.pageCount)]);
  if (version.method) rows.push([t("viewer.method"), t(`methods.${version.method}`)]);
  if (version.ocrConfidence !== null) {
    rows.push([t("viewer.ocrConfidence"), `${Math.round(version.ocrConfidence * PERCENT)}%`]);
  }
  if (version.blockCount !== null) rows.push([t("viewer.blocks"), String(version.blockCount)]);
  rows.push([
    t("viewer.uploaded"),
    format.dateTime(new Date(version.uploadedAt), { dateStyle: "medium", timeStyle: "short" }),
  ]);
  if (page && page.marginTopMm !== null) {
    const margins = t("viewer.margins", {
      top: Math.round(page.marginTopMm),
      bottom: Math.round(page.marginBottomMm ?? 0),
      left: Math.round(page.marginLeftMm ?? 0),
      right: Math.round(page.marginRightMm ?? 0),
    });
    const source =
      page.source === "declared" ? t("viewer.layoutDeclared") : t("viewer.layoutMeasured");
    rows.push([t("viewer.layout"), `${margins} (${source})`]);
  }
  return <Facts items={rows.map(([term, value]) => ({ term, value }))} />;
}
