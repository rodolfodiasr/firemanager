import apiClient from "./client";

export interface TenantOverview {
  id: string;
  name: string;
  slug: string;
  device_count: number;
  online_count: number;
  pending_ops: number;
  last_seen: string | null;
}

export interface SupportTokenResponse {
  access_token: string;
  tenant_id: string;
  tenant_name: string;
}

export const adminApi = {
  getTenantsOverview: () =>
    apiClient.get<TenantOverview[]>("/admin/tenants/overview").then((r) => r.data),

  getSupportToken: (tenantId: string) =>
    apiClient
      .post<SupportTokenResponse>(`/admin/tenants/${tenantId}/support-token`)
      .then((r) => r.data),
};
