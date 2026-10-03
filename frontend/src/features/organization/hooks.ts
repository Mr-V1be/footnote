"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { useMembership } from "@/features/session/membership";
import { useApi } from "@/shared/api/ApiProvider";
import type { Role } from "@/shared/api/types";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import type { SelectOption } from "@/shared/ui/select/Select";

import { adminKeys, fetchAdministrationCatalog } from "./queries";

export function useOrganizationAlias(): string {
  return useMembership().membership.organization.alias;
}

/** Roles, scopes, events and categories: registries of the server, read once. */
export function useAdministrationCatalog() {
  const api = useApi();
  return useQuery({
    queryKey: adminKeys.catalog(),
    queryFn: () => fetchAdministrationCatalog(api),
    staleTime: Infinity,
  });
}

/** Roles to choose from, highest first. */
export function useRoleOptions(): SelectOption[] {
  const catalog = useAdministrationCatalog();
  const roleLabel = useCodeLabel("roles");
  return useMemo(
    () =>
      (catalog.data?.roles ?? []).map((role) => ({
        value: role.code,
        label: roleLabel(role.code),
      })),
    [catalog.data, roleLabel],
  );
}

/** The role a newcomer gets by default: the least one that may upload documents. */
export function defaultRole(roles: readonly Role[]): string {
  const workers = roles
    .filter((role) => role.permissions.includes("documents.upload"))
    .sort((a, b) => a.permissions.length - b.permissions.length);
  return workers[0]?.code ?? roles.at(-1)?.code ?? "";
}
