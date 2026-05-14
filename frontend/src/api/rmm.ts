import api from "./index";

export type RmmType = "tactical_rmm" | "ninja_rmm" | "atera" | "connectwise_automate";

export interface RmmIntegration {
  id: string;
  name: string;
  rmm_type: RmmType;
  base_url: string;
  verify_ssl: boolean;
  is_active: boolean;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_message: string | null;
  agent_count: number;
  created_at: string;
}

export interface RmmAgent {
  id: string;
  integration_id: string;
  external_id: string;
  hostname: string;
  os_name: string | null;
  ip_address: string | null;
  status: string;
  last_seen: string | null;
  patches_pending: number | null;
  alerts_count: number;
  synced_at: string;
}

export const rmmApi = {
  list: () => api.get<RmmIntegration[]>("/rmm").then((r) => r.data),

  create: (data: {
    name: string;
    rmm_type: RmmType;
    base_url: string;
    credentials: Record<string, string>;
    verify_ssl?: boolean;
  }) => api.post<RmmIntegration>("/rmm", data).then((r) => r.data),

  update: (id: string, data: Partial<RmmIntegration & { credentials: Record<string, string> }>) =>
    api.patch<RmmIntegration>(`/rmm/${id}`, data).then((r) => r.data),

  delete: (id: string) => api.delete(`/rmm/${id}`),

  test: (id: string) =>
    api.post<{ ok: boolean; message: string }>(`/rmm/${id}/test`).then((r) => r.data),

  sync: (id: string) =>
    api.post<{ synced: number; message: string }>(`/rmm/${id}/sync`).then((r) => r.data),

  agents: (id: string) =>
    api.get<RmmAgent[]>(`/rmm/${id}/agents`).then((r) => r.data),
};

export const ssoMappingsApi = {
  list: () => api.get("/sso-mappings").then((r) => r.data),
  create: (data: { external_group: string; platform_role: string }) =>
    api.post("/sso-mappings", data).then((r) => r.data),
  delete: (id: string) => api.delete(`/sso-mappings/${id}`),
  roles: () => api.get<{ roles: string[] }>("/sso-mappings/roles").then((r) => r.data),
};

export const fileSharesApi = {
  list: () => api.get("/file-shares").then((r) => r.data),
  create: (data: object) => api.post("/file-shares", data).then((r) => r.data),
  delete: (id: string) => api.delete(`/file-shares/${id}`),
  getScript: (id: string) => api.get<{ script: string; language: string }>(`/file-shares/${id}/script`).then((r) => r.data),
  submitScan: (id: string, data: { shares: object[]; acls: object[] }) =>
    api.post(`/file-shares/${id}/scan-result`, data).then((r) => r.data),
  shares: (id: string) => api.get(`/file-shares/${id}/shares`).then((r) => r.data),
  acls: (configId: string, shareId: string) =>
    api.get(`/file-shares/${configId}/shares/${shareId}/acls`).then((r) => r.data),
};

export const syslogApi = {
  list: () => api.get("/siem-syslog").then((r) => r.data),
  create: (data: object) => api.post("/siem-syslog", data).then((r) => r.data),
  update: (id: string, data: object) => api.patch(`/siem-syslog/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/siem-syslog/${id}`),
  test: (id: string) =>
    api.post<{ ok: boolean; message: string }>(`/siem-syslog/${id}/test`).then((r) => r.data),
};
