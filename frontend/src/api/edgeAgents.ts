import apiClient from "./client";

export interface EdgeAgent {
  id: string;
  name: string;
  status: "online" | "offline" | "stale";
  version: string | null;
  last_seen: string | null;
  ip_address: string | null;
  device_ids: string[] | null;
  notes: string | null;
  created_at: string;
}

export interface EdgeAgentWithToken extends EdgeAgent {
  token: string;
}

export interface SsoConfig {
  id: string;
  provider: string;
  client_id: string;
  discovery_url: string;
  group_claim: string | null;
  group_mapping: Record<string, string> | null;
  sso_required: boolean;
  is_active: boolean;
  created_at: string;
}

export interface MarketplacePlugin {
  id: string;
  name: string;
  slug: string;
  version: string;
  category: string;
  description: string | null;
  is_builtin: boolean;
  download_count: number;
  approved_at: string | null;
}

export interface TenantPlugin {
  id: string;
  plugin_id: string;
  installed_at: string;
  plugin: MarketplacePlugin;
}

export interface RbacCustomRole {
  id: string;
  name: string;
  description: string | null;
  permissions: Record<string, unknown> | null;
  created_at: string;
}

export interface RbacRoleAssignment {
  id: string;
  user_id: string;
  role_id: string;
  assigned_at: string;
}

const BASE = "/platform";

export const edgeAgentsApi = {
  // Edge Agents
  listAgents: () =>
    apiClient.get<EdgeAgent[]>(`${BASE}/agents`).then(r => r.data),
  createAgent: (data: { name: string; notes?: string }) =>
    apiClient.post<EdgeAgentWithToken>(`${BASE}/agents`, data).then(r => r.data),
  updateAgent: (id: string, data: { name: string; notes?: string }) =>
    apiClient.patch<EdgeAgent>(`${BASE}/agents/${id}`, data).then(r => r.data),
  deleteAgent: (id: string) => apiClient.delete(`${BASE}/agents/${id}`),

  // SSO
  getSsoConfig: () =>
    apiClient.get<SsoConfig | null>(`${BASE}/sso`).then(r => r.data),
  upsertSsoConfig: (data: { provider?: string; client_id: string; client_secret?: string; discovery_url: string; group_claim?: string; group_mapping?: Record<string, string>; sso_required?: boolean }) =>
    apiClient.put<SsoConfig>(`${BASE}/sso`, data).then(r => r.data),
  deleteSsoConfig: () => apiClient.delete(`${BASE}/sso`),

  // Marketplace
  listMarketplace: () =>
    apiClient.get<MarketplacePlugin[]>(`${BASE}/marketplace`).then(r => r.data),
  seedMarketplace: () =>
    apiClient.post<MarketplacePlugin[]>(`${BASE}/marketplace/seed`).then(r => r.data),
  listInstalled: () =>
    apiClient.get<TenantPlugin[]>(`${BASE}/marketplace/installed`).then(r => r.data),
  installPlugin: (pluginId: string) =>
    apiClient.post<TenantPlugin>(`${BASE}/marketplace/${pluginId}/install`).then(r => r.data),
  uninstallPlugin: (pluginId: string) =>
    apiClient.delete(`${BASE}/marketplace/${pluginId}/uninstall`),

  // RBAC
  listRoles: () =>
    apiClient.get<RbacCustomRole[]>(`${BASE}/rbac-roles`).then(r => r.data),
  createRole: (data: { name: string; description?: string; permissions?: Record<string, unknown> }) =>
    apiClient.post<RbacCustomRole>(`${BASE}/rbac-roles`, data).then(r => r.data),
  deleteRole: (id: string) => apiClient.delete(`${BASE}/rbac-roles/${id}`),
  listAssignments: () =>
    apiClient.get<RbacRoleAssignment[]>(`${BASE}/rbac-assignments`).then(r => r.data),
  assignRole: (data: { user_id: string; role_id: string }) =>
    apiClient.post<RbacRoleAssignment>(`${BASE}/rbac-assignments`, data).then(r => r.data),
  removeAssignment: (id: string) => apiClient.delete(`${BASE}/rbac-assignments/${id}`),
};
