import apiClient from "./client";

export interface VaultConfig {
  id: string;
  name: string;
  vault_url: string;
  auth_method: string;
  role_id: string | null;
  default_mount: string;
  namespace: string | null;
  is_active: boolean;
  last_verified_at: string | null;
  last_verified_ok: boolean | null;
  created_at: string;
}

export interface VaultSecretRef {
  id: string;
  vault_config_id: string;
  alias: string;
  vault_path: string;
  vault_key: string;
  description: string | null;
  category: string | null;
  created_at: string;
}

export interface OpaPolicy {
  id: string;
  name: string;
  description: string | null;
  package_name: string;
  rego_source: string;
  category: string | null;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface OpaEvaluation {
  id: string;
  policy_name: string;
  input_data: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  allowed: boolean | null;
  evaluated_at: string;
}

export interface SecurityProfile {
  id: string;
  name: string;
  profile_type: string;
  controls: Record<string, unknown> | null;
  status: string;
  applied_at: string | null;
  notes: string | null;
  created_at: string;
}

export interface PentestSchedule {
  id: string;
  title: string;
  scope: string | null;
  pentest_type: string;
  vendor: string | null;
  scheduled_at: string | null;
  completed_at: string | null;
  status: string;
  findings_critical: number;
  findings_high: number;
  findings_medium: number;
  findings_low: number;
  report_url: string | null;
  remediation_deadline: string | null;
  created_at: string;
}

const BASE = "/security-infra";

export const securityInfraApi = {
  // Vault Configs
  listVaultConfigs: () =>
    apiClient.get<VaultConfig[]>(`${BASE}/vault-configs`).then(r => r.data),
  createVaultConfig: (data: { name: string; vault_url: string; auth_method?: string; token?: string; default_mount?: string; namespace?: string }) =>
    apiClient.post<VaultConfig>(`${BASE}/vault-configs`, data).then(r => r.data),
  deleteVaultConfig: (id: string) => apiClient.delete(`${BASE}/vault-configs/${id}`),

  // Vault Secret Refs
  listSecretRefs: (configId: string) =>
    apiClient.get<VaultSecretRef[]>(`${BASE}/vault-configs/${configId}/secrets`).then(r => r.data),
  createSecretRef: (configId: string, data: { alias: string; vault_path: string; vault_key?: string; description?: string; category?: string }) =>
    apiClient.post<VaultSecretRef>(`${BASE}/vault-configs/${configId}/secrets`, data).then(r => r.data),
  deleteSecretRef: (configId: string, refId: string) =>
    apiClient.delete(`${BASE}/vault-configs/${configId}/secrets/${refId}`),

  // OPA Policies
  listPolicies: () =>
    apiClient.get<OpaPolicy[]>(`${BASE}/opa-policies`).then(r => r.data),
  seedPolicies: () =>
    apiClient.post<OpaPolicy[]>(`${BASE}/opa-policies/seed`).then(r => r.data),
  createPolicy: (data: { name: string; package_name?: string; rego_source: string; description?: string; category?: string }) =>
    apiClient.post<OpaPolicy>(`${BASE}/opa-policies`, data).then(r => r.data),
  evaluatePolicy: (policyId: string, inputData: Record<string, unknown>) =>
    apiClient.post<OpaEvaluation>(`${BASE}/opa-policies/${policyId}/evaluate`, { input_data: inputData }).then(r => r.data),
  deletePolicy: (id: string) => apiClient.delete(`${BASE}/opa-policies/${id}`),

  // Security Profiles
  listProfiles: () =>
    apiClient.get<SecurityProfile[]>(`${BASE}/security-profiles`).then(r => r.data),
  createProfile: (data: { name: string; profile_type?: string; controls?: Record<string, unknown>; notes?: string }) =>
    apiClient.post<SecurityProfile>(`${BASE}/security-profiles`, data).then(r => r.data),
  updateProfile: (id: string, data: Partial<SecurityProfile>) =>
    apiClient.patch<SecurityProfile>(`${BASE}/security-profiles/${id}`, data).then(r => r.data),
  applyProfile: (id: string) =>
    apiClient.post<SecurityProfile>(`${BASE}/security-profiles/${id}/apply`).then(r => r.data),
  deleteProfile: (id: string) => apiClient.delete(`${BASE}/security-profiles/${id}`),

  // Pentest Schedules
  listPentests: () =>
    apiClient.get<PentestSchedule[]>(`${BASE}/pentest-schedules`).then(r => r.data),
  createPentest: (data: { title: string; scope?: string; pentest_type?: string; vendor?: string; scheduled_at?: string }) =>
    apiClient.post<PentestSchedule>(`${BASE}/pentest-schedules`, data).then(r => r.data),
  updatePentest: (id: string, data: Partial<PentestSchedule>) =>
    apiClient.patch<PentestSchedule>(`${BASE}/pentest-schedules/${id}`, data).then(r => r.data),
  deletePentest: (id: string) => apiClient.delete(`${BASE}/pentest-schedules/${id}`),
};
