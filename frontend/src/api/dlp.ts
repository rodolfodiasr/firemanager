import apiClient from "./client";

export interface DLPConfig {
  id: string;
  tenant_id: string;
  enabled: boolean;
  compliance_mode: boolean;
  incident_threshold_count: number;
  incident_threshold_hours: number;
}

export interface DLPRule {
  id: string;
  rule_key: string;
  rule_name: string;
  description: string | null;
  category: "pii_br" | "credentials" | "infra_mssp" | "custom";
  action: "block" | "warn";
  is_enabled: boolean;
  is_builtin: boolean;
  pattern: string | null;
}

export interface DLPIncident {
  id: string;
  pii_type: string;
  action_taken: "block" | "warn";
  source: string;
  ip_address: string | null;
  user_id: string | null;
  created_at: string;
}

export interface DLPRuleCreate {
  rule_key: string;
  rule_name: string;
  description?: string;
  category?: string;
  action: "block" | "warn";
  pattern: string;
}

const qs = (tenantId?: string) => (tenantId ? `?tenant_id=${tenantId}` : "");

export const dlpApi = {
  getConfig: (tenantId?: string): Promise<DLPConfig> =>
    apiClient.get(`/dlp/config${qs(tenantId)}`).then((r) => r.data),

  updateConfig: (
    data: Partial<Pick<DLPConfig, "enabled" | "compliance_mode" | "incident_threshold_count" | "incident_threshold_hours">>,
    tenantId?: string,
  ): Promise<DLPConfig> =>
    apiClient.put(`/dlp/config${qs(tenantId)}`, data).then((r) => r.data),

  listRules: (tenantId?: string): Promise<DLPRule[]> =>
    apiClient.get(`/dlp/rules${qs(tenantId)}`).then((r) => r.data),

  updateRule: (ruleId: string, data: { action?: "block" | "warn"; is_enabled?: boolean }, tenantId?: string): Promise<DLPRule> =>
    apiClient.put(`/dlp/rules/${ruleId}${qs(tenantId)}`, data).then((r) => r.data),

  createRule: (data: DLPRuleCreate, tenantId?: string): Promise<DLPRule> =>
    apiClient.post(`/dlp/rules${qs(tenantId)}`, data).then((r) => r.data),

  deleteRule: (ruleId: string, tenantId?: string): Promise<void> =>
    apiClient.delete(`/dlp/rules/${ruleId}${qs(tenantId)}`).then(() => undefined),

  listIncidents: (tenantId?: string, limit = 50): Promise<DLPIncident[]> =>
    apiClient.get(`/dlp/incidents${qs(tenantId)}&limit=${limit}`).then((r) => r.data),
};
