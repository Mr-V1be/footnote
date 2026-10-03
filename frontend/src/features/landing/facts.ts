import type { CheckCatalog } from "@/shared/api/types";

/**
 * The most checks one document gets: the set depends on the document's
 * kind, so the catalog's total would overstate it.
 */
export function mostChecksPerDocument(catalog: CheckCatalog): number {
  const perKind = new Map<string, number>();
  for (const check of catalog.checks) {
    for (const kind of check.kinds) perKind.set(kind, (perKind.get(kind) ?? 0) + 1);
  }
  return Math.max(0, ...perKind.values());
}
