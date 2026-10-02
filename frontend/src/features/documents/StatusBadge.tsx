"use client";

import { useTranslations } from "next-intl";

import type { ParseFailureCode, ParseStatus } from "@/shared/api/types";
import { Badge, type BadgeTone } from "@/shared/ui/badge/Badge";
import { Tooltip } from "@/shared/ui/tooltip/Tooltip";

const TONES: Record<ParseStatus, BadgeTone> = {
  queued: "neutral",
  parsing: "ink",
  parsed: "success",
  failed: "critical",
};

export function StatusBadge({
  status,
  failure,
}: {
  status: ParseStatus;
  failure?: ParseFailureCode | null;
}) {
  const t = useTranslations();
  const badge = (
    <span>
      <Badge tone={TONES[status]} dot pulse={status === "queued" || status === "parsing"}>
        {t(`status.${status}`)}
      </Badge>
    </span>
  );
  return failure ? <Tooltip content={t(`failures.${failure}`)}>{badge}</Tooltip> : badge;
}
