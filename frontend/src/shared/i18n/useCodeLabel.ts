"use client";

import { useTranslations } from "next-intl";
import { useCallback } from "react";

import type { Messages } from "./messages";

/** Namespaces whose keys are codes of open, server-side registries. */
type RegistryNamespace =
  | "roles"
  | "kinds"
  | "formats"
  | "families"
  | "familiesShort"
  | "plans"
  | "usageMetrics"
  | "auditActions"
  | "auditCategories"
  | "actorKinds"
  | "apiScopes"
  | "webhookEvents"
  | "healthChecks";

/**
 * Label for a registry code. Registries live on the server and may gain
 * values before the catalogue does; such codes are shown as they are.
 * A dot nests keys in the catalogue, so codes with dots ("check.completed")
 * are kept there with underscores ("check_completed").
 */
export function useCodeLabel(namespace: RegistryNamespace): (code: string) => string {
  const t = useTranslations(namespace);
  return useCallback(
    (code: string) => {
      const key = code.replaceAll(".", "_") as keyof Messages[RegistryNamespace];
      return t.has(key) ? t(key) : code;
    },
    [t],
  );
}
