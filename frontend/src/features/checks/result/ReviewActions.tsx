"use client";

import { IconArrowBackUp, IconCheck, IconChecks, IconX } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { useCan } from "@/features/session/membership";
import type { Finding, Permission, ReviewStatus } from "@/shared/api/types";
import { Badge, type BadgeTone } from "@/shared/ui/badge/Badge";
import { Button } from "@/shared/ui/button/Button";

import styles from "./finding-card.module.css";

interface Action {
  review: ReviewStatus;
  label: "accept" | "reject" | "fix";
  icon: ReactNode;
  permission: Permission;
}

// Mirrors the server's rule: a legal judgement for accept and reject, work on
// the document for "fixed". The server decides; this only hides what would fail.
const ACTIONS: readonly Action[] = [
  {
    review: "accepted",
    label: "accept",
    icon: <IconCheck stroke={1.75} />,
    permission: "findings.decide",
  },
  {
    review: "rejected",
    label: "reject",
    icon: <IconX stroke={1.75} />,
    permission: "findings.decide",
  },
  {
    review: "fixed",
    label: "fix",
    icon: <IconChecks stroke={1.75} />,
    permission: "findings.resolve",
  },
];

const STATUS_TONE: Record<ReviewStatus, BadgeTone> = {
  open: "neutral",
  accepted: "ink",
  rejected: "neutral",
  fixed: "success",
};

export function ReviewActions({
  finding,
  busy,
  onReview,
}: {
  finding: Finding;
  busy: boolean;
  onReview: (review: ReviewStatus) => void;
}) {
  const t = useTranslations("checks");
  const canDecide = useCan("findings.decide");
  const canResolve = useCan("findings.resolve");
  const allowed = (permission: Permission) =>
    permission === "findings.decide" ? canDecide : canResolve;

  if (finding.review !== "open") {
    return (
      <div className={styles.decision}>
        <Badge tone={STATUS_TONE[finding.review]} dot>
          {t(`review.${finding.review}`)}
        </Badge>
        {canResolve ? (
          <Button
            variant="ghost"
            size="sm"
            icon={<IconArrowBackUp stroke={1.75} />}
            disabled={busy}
            onClick={() => onReview("open")}
          >
            {t("actions.reopen")}
          </Button>
        ) : null}
      </div>
    );
  }
  const available = ACTIONS.filter((action) => allowed(action.permission));
  if (available.length === 0) return null;
  return (
    <div className={styles.actions} role="group" aria-label={t("actions.label")}>
      {available.map((action) => (
        <Button
          key={action.review}
          variant="secondary"
          size="sm"
          icon={action.icon}
          disabled={busy}
          onClick={() => onReview(action.review)}
        >
          {t(`actions.${action.label}`)}
        </Button>
      ))}
    </div>
  );
}
