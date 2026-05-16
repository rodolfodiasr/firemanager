import apiClient from "./client";

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
  site_filter: string | null;
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
  raw_data?: Record<string, unknown> | null;
}

export interface RmmScriptRun {
  id: string;
  integration_id: string;
  agent_external_id: string;
  agent_hostname: string;
  run_type: "script" | "command";
  shell: string;
  body: string;
  output: string | null;
  exit_code: number | null;
  status: "pending" | "running" | "success" | "error";
  started_at: string;
  finished_at: string | null;
}

export const rmmApi = {
  list: () => apiClient.get<RmmIntegration[]>("/rmm").then((r) => r.data),

  create: (data: {
    name: string;
    rmm_type: RmmType;
    base_url: string;
    credentials: Record<string, string>;
    verify_ssl?: boolean;
    site_filter?: string | null;
  }) => apiClient.post<RmmIntegration>("/rmm", data).then((r) => r.data),

  update: (id: string, data: Partial<RmmIntegration & { credentials: Record<string, string> }>) =>
    apiClient.patch<RmmIntegration>(`/rmm/${id}`, data).then((r) => r.data),

  delete: (id: string) => apiClient.delete(`/rmm/${id}`),

  test: (id: string) =>
    apiClient.post<{ ok: boolean; message: string }>(`/rmm/${id}/test`).then((r) => r.data),

  sync: (id: string) =>
    apiClient.post<{ synced: number; message: string }>(`/rmm/${id}/sync`).then((r) => r.data),

  agents: (id: string, status?: string) =>
    apiClient.get<RmmAgent[]>(`/rmm/${id}/agents`, { params: status ? { status } : undefined }).then((r) => r.data),

  run: (integrationId: string, agentExternalId: string, data: {
    run_type: "script" | "command";
    shell: string;
    body: string;
    timeout: number;
  }) =>
    apiClient
      .post<RmmScriptRun>(`/rmm/${integrationId}/agents/${agentExternalId}/run`, data)
      .then((r) => r.data),

  scriptRuns: (integrationId: string, agentId?: string) =>
    apiClient
      .get<RmmScriptRun[]>(`/rmm/${integrationId}/script-runs`, {
        params: agentId ? { agent_id: agentId } : undefined,
      })
      .then((r) => r.data),
};

export type TemplateCategory = "monitoring" | "security" | "maintenance" | "network" | "general" | "incident_response" | "identity" | "compliance" | "forensics";
export type TemplateShell = "powershell" | "cmd" | "python" | "bash";

export interface RmmScriptTemplate {
  id: string;
  tenant_id: string | null;
  name: string;
  description: string | null;
  category: TemplateCategory;
  shell: TemplateShell;
  run_type: "command" | "script";
  body: string;
  is_builtin: boolean;
  created_at: string;
}

export const rmmTemplatesApi = {
  list: (category?: string) =>
    apiClient
      .get<RmmScriptTemplate[]>("/rmm/templates", { params: category ? { category } : undefined })
      .then((r) => r.data),

  seed: () =>
    apiClient.post<{ added: number; message: string }>("/rmm/templates/seed").then((r) => r.data),

  create: (data: {
    name: string;
    body: string;
    shell: string;
    run_type: string;
    category: string;
    description?: string;
  }) => apiClient.post<RmmScriptTemplate>("/rmm/templates", data).then((r) => r.data),

  update: (id: string, data: Partial<Omit<RmmScriptTemplate, "id" | "tenant_id" | "is_builtin" | "created_at">>) =>
    apiClient.patch<RmmScriptTemplate>(`/rmm/templates/${id}`, data).then((r) => r.data),

  delete: (id: string) => apiClient.delete(`/rmm/templates/${id}`),
};

export const ssoMappingsApi = {
  list: () => apiClient.get("/sso-mappings").then((r) => r.data),
  create: (data: { external_group: string; platform_role: string }) =>
    apiClient.post("/sso-mappings", data).then((r) => r.data),
  delete: (id: string) => apiClient.delete(`/sso-mappings/${id}`),
  roles: () => apiClient.get<{ roles: string[] }>("/sso-mappings/roles").then((r) => r.data),
};

export const fileSharesApi = {
  list: () => apiClient.get("/file-shares").then((r) => r.data),
  create: (data: object) => apiClient.post("/file-shares", data).then((r) => r.data),
  delete: (id: string) => apiClient.delete(`/file-shares/${id}`),
  getScript: (id: string) => apiClient.get<{ script: string; language: string }>(`/file-shares/${id}/script`).then((r) => r.data),
  submitScan: (id: string, data: { shares: object[]; acls: object[] }) =>
    apiClient.post(`/file-shares/${id}/scan-result`, data).then((r) => r.data),
  shares: (id: string) => apiClient.get(`/file-shares/${id}/shares`).then((r) => r.data),
  acls: (configId: string, shareId: string) =>
    apiClient.get(`/file-shares/${configId}/shares/${shareId}/acls`).then((r) => r.data),
};

export const syslogApi = {
  list: () => apiClient.get("/siem-syslog").then((r) => r.data),
  create: (data: object) => apiClient.post("/siem-syslog", data).then((r) => r.data),
  update: (id: string, data: object) => apiClient.patch(`/siem-syslog/${id}`, data).then((r) => r.data),
  delete: (id: string) => apiClient.delete(`/siem-syslog/${id}`),
  test: (id: string) =>
    apiClient.post<{ ok: boolean; message: string }>(`/siem-syslog/${id}/test`).then((r) => r.data),
};
