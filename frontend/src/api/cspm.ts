import apiClient from "./client";

export interface CloudAccount {
  id: string;
  name: string;
  provider: string;
  region: string | null;
  is_active: boolean;
  last_sync_at: string | null;
  last_sync_status: string | null;
  created_at: string;
}

export interface CloudAccountCreate {
  name: string;
  provider: string;
  credentials?: Record<string, unknown>;
  region?: string;
}

export interface CloudFinding {
  id: string;
  account_id: string;
  resource_type: string;
  resource_id: string;
  resource_name: string | null;
  check_id: string;
  check_title: string;
  severity: string;
  status: string;
  detected_at: string;
}

export const cspmApi = {
  listAccounts: () =>
    apiClient.get<CloudAccount[]>("/cloud-accounts").then((r) => r.data),

  createAccount: (data: CloudAccountCreate) =>
    apiClient.post<CloudAccount>("/cloud-accounts", data).then((r) => r.data),

  updateAccount: (id: string, data: CloudAccountCreate) =>
    apiClient.patch<CloudAccount>(`/cloud-accounts/${id}`, data).then((r) => r.data),

  deleteAccount: (id: string) =>
    apiClient.delete(`/cloud-accounts/${id}`),

  syncAccount: (id: string) =>
    apiClient.post<{ resources_synced: number; findings_created: number; status: string }>(
      `/cloud-accounts/${id}/sync`
    ).then((r) => r.data),

  listFindings: (params?: { severity?: string; status?: string; account_id?: string; limit?: number }) =>
    apiClient.get<CloudFinding[]>("/cloud-accounts/findings/list", { params }).then((r) => r.data),

  acceptFinding: (id: string, reason: string) =>
    apiClient.post<CloudFinding>(`/cloud-accounts/findings/${id}/accept`, { reason }).then((r) => r.data),

  resolveFinding: (id: string) =>
    apiClient.post<CloudFinding>(`/cloud-accounts/findings/${id}/resolve`).then((r) => r.data),
};
