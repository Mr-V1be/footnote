"use client";

import { useSearchParams } from "next/navigation";

import type { ActorKind } from "@/shared/api/types";
import { useReplaceParams } from "@/shared/hooks/useReplaceParams";

import type { AuditFilters } from "../queries";

/** Periods to look back, in days; null is the whole log. */
export const AUDIT_PERIODS = [7, 30, 90, null] as const;
const DEFAULT_PERIOD = 30;

/** The log's filters, kept in the address. */
export function useAuditFilters(): {
  filters: AuditFilters;
  set: (next: Partial<AuditFilters>) => void;
} {
  const params = useSearchParams();
  const replace = useReplaceParams();
  const period = params.get("period");
  const filters: AuditFilters = {
    category: params.get("category"),
    actorKind: (params.get("actor") as ActorKind | null) ?? null,
    days: period === "all" ? null : Number(period) || DEFAULT_PERIOD,
  };
  return {
    filters,
    set: (next) =>
      replace({
        ...("category" in next ? { category: next.category ?? null } : {}),
        ...("actorKind" in next ? { actor: next.actorKind ?? null } : {}),
        ...("days" in next ? { period: next.days === null ? "all" : String(next.days) } : {}),
      }),
  };
}
