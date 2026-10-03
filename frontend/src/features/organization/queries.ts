import { BFF_PREFIX, type ApiClient } from "@/shared/api/client";
import { unwrap, unwrapEmpty } from "@/shared/api/errors";
import type {
  ActorKind,
  AdministrationCatalog,
  AuditPage,
  Invite,
  Member,
  Workspace,
  WorkspaceInput,
  WorkspaceMember,
  WorkspacePatch,
} from "@/shared/api/types";

export const AUDIT_PAGE_SIZE = 50;

export interface AuditFilters {
  category: string | null;
  actorKind: ActorKind | null;
  /** Days back from today; null for all time. */
  days: number | null;
}

export const adminKeys = {
  catalog: () => ["administration", "catalog"] as const,
  organization: (organization: string) => ["organizations", organization, "admin"] as const,
  members: (organization: string) => [...adminKeys.organization(organization), "members"] as const,
  workspaces: (organization: string) => ["organizations", organization, "workspaces"] as const,
  workspaceMembers: (organization: string, workspaceId: string) =>
    [...adminKeys.organization(organization), "workspace-members", workspaceId] as const,
  audit: (organization: string, filters: AuditFilters) =>
    [...adminKeys.organization(organization), "audit", filters] as const,
};

export async function fetchAdministrationCatalog(api: ApiClient): Promise<AdministrationCatalog> {
  return unwrap(await api.GET("/api/v1/administration/catalog"));
}

const org = (organization: string) => ({ params: { path: { organization } } });

export async function fetchMembers(api: ApiClient, organization: string): Promise<Member[]> {
  return unwrap(await api.GET("/api/v1/organizations/{organization}/members", org(organization)));
}

export async function inviteMember(
  api: ApiClient,
  organization: string,
  invite: Invite,
): Promise<Member> {
  return unwrap(
    await api.POST("/api/v1/organizations/{organization}/members", {
      ...org(organization),
      body: invite,
    }),
  );
}

export async function changeMemberRole(
  api: ApiClient,
  organization: string,
  userId: string,
  role: string,
): Promise<Member> {
  return unwrap(
    await api.PATCH("/api/v1/organizations/{organization}/members/{user_id}", {
      params: { path: { organization, user_id: userId } },
      body: { role },
    }),
  );
}

export async function removeMember(
  api: ApiClient,
  organization: string,
  userId: string,
): Promise<void> {
  unwrapEmpty(
    await api.DELETE("/api/v1/organizations/{organization}/members/{user_id}", {
      params: { path: { organization, user_id: userId } },
    }),
  );
}

export async function fetchWorkspaces(api: ApiClient, organization: string): Promise<Workspace[]> {
  return unwrap(
    await api.GET("/api/v1/organizations/{organization}/workspaces", org(organization)),
  );
}

export async function createWorkspace(
  api: ApiClient,
  organization: string,
  input: WorkspaceInput,
): Promise<Workspace> {
  return unwrap(
    await api.POST("/api/v1/organizations/{organization}/workspaces", {
      ...org(organization),
      body: input,
    }),
  );
}

export async function updateWorkspace(
  api: ApiClient,
  organization: string,
  workspaceId: string,
  patch: WorkspacePatch,
): Promise<Workspace> {
  return unwrap(
    await api.PATCH("/api/v1/organizations/{organization}/workspaces/{workspace_id}", {
      params: { path: { organization, workspace_id: workspaceId } },
      body: patch,
    }),
  );
}

export async function deleteWorkspace(
  api: ApiClient,
  organization: string,
  workspaceId: string,
): Promise<void> {
  unwrapEmpty(
    await api.DELETE("/api/v1/organizations/{organization}/workspaces/{workspace_id}", {
      params: { path: { organization, workspace_id: workspaceId } },
    }),
  );
}

export async function fetchWorkspaceMembers(
  api: ApiClient,
  organization: string,
  workspaceId: string,
): Promise<WorkspaceMember[]> {
  return unwrap(
    await api.GET("/api/v1/organizations/{organization}/workspaces/{workspace_id}/members", {
      params: { path: { organization, workspace_id: workspaceId } },
    }),
  );
}

export async function setWorkspaceMember(
  api: ApiClient,
  organization: string,
  workspaceId: string,
  userId: string,
  role: string,
): Promise<WorkspaceMember> {
  return unwrap(
    await api.PUT(
      "/api/v1/organizations/{organization}/workspaces/{workspace_id}/members/{user_id}",
      {
        params: { path: { organization, workspace_id: workspaceId, user_id: userId } },
        body: { role },
      },
    ),
  );
}

export async function removeWorkspaceMember(
  api: ApiClient,
  organization: string,
  workspaceId: string,
  userId: string,
): Promise<void> {
  unwrapEmpty(
    await api.DELETE(
      "/api/v1/organizations/{organization}/workspaces/{workspace_id}/members/{user_id}",
      { params: { path: { organization, workspace_id: workspaceId, user_id: userId } } },
    ),
  );
}

function auditQuery(filters: AuditFilters, now: Date) {
  const since =
    filters.days === null
      ? undefined
      : new Date(now.getTime() - filters.days * 24 * 60 * 60 * 1000).toISOString();
  return {
    ...(filters.category ? { category: [filters.category] } : {}),
    ...(filters.actorKind ? { actorKind: filters.actorKind } : {}),
    ...(since ? { since } : {}),
  };
}

export async function fetchAuditPage(
  api: ApiClient,
  organization: string,
  filters: AuditFilters,
  now: Date,
  cursor: string | null,
): Promise<AuditPage> {
  return unwrap(
    await api.GET("/api/v1/organizations/{organization}/audit", {
      params: {
        path: { organization },
        query: {
          ...auditQuery(filters, now),
          limit: AUDIT_PAGE_SIZE,
          ...(cursor ? { cursor } : {}),
        },
      },
    }),
  );
}

/** The log as CSV with the same filters, downloaded through the web server. */
export function auditExportUrl(organization: string, filters: AuditFilters, now: Date): string {
  const { category, ...rest } = auditQuery(filters, now);
  const query = new URLSearchParams(rest);
  for (const value of category ?? []) query.append("category", value);
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return `${BFF_PREFIX}/api/v1/organizations/${organization}/audit/export${suffix}`;
}
