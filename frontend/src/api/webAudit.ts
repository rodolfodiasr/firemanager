import apiClient from "./client";

export interface WebAuditConfig {
  id: string;
  tenant_id: string;
  enabled: boolean;
  collection_method: string;
  gpo_share_path: string | null;
  poll_interval_minutes: number;
  retention_days: number;
  alert_on_malicious: boolean;
  alert_on_shadow_it: boolean;
}

export interface WebAuditEntry {
  id: string;
  workstation: string;
  ad_user: string | null;
  department: string | null;
  url: string;
  domain: string;
  visited_at: string;
  browser: string | null;
  title: string | null;
  visit_count: number;
  category: string;
  ai_analyzed: boolean;
}

export interface WebAuditFinding {
  id: string;
  workstation: string;
  ad_user: string | null;
  finding_type: string;
  severity: string;
  domain: string;
  description: string;
  recommendation: string | null;
  ai_confidence: number | null;
  soar_triggered: boolean;
  created_at: string;
}

export interface UserRiskSummary {
  ad_user: string;
  department: string | null;
  total_visits: number;
  malicious_count: number;
  shadow_it_count: number;
  productivity_score: number;
  risk_level: string;
}

export interface DomainStats {
  domain: string;
  category: string;
  visit_count: number;
  unique_users: number;
}

const base = "/web-audit";

export const webAuditApi = {
  getConfig: () => apiClient.get<WebAuditConfig>(`${base}/config`).then(r => r.data),
  updateConfig: (data: Partial<WebAuditConfig>) => apiClient.put<WebAuditConfig>(`${base}/config`, data).then(r => r.data),

  uploadHistory: (file: File, workstation: string, adUser?: string, department?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    const params = new URLSearchParams({ workstation });
    if (adUser) params.set("ad_user", adUser);
    if (department) params.set("department", department);
    return apiClient.post<{ ingested: number }>(`${base}/upload?${params}`, fd, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then(r => r.data);
  },

  getEntries: (params?: { workstation?: string; ad_user?: string; category?: string; days?: number; limit?: number }) =>
    apiClient.get<WebAuditEntry[]>(`${base}/entries`, { params }).then(r => r.data),

  getFindings: (params?: { severity?: string; finding_type?: string; limit?: number }) =>
    apiClient.get<WebAuditFinding[]>(`${base}/findings`, { params }).then(r => r.data),

  getUserStats: (days?: number) =>
    apiClient.get<UserRiskSummary[]>(`${base}/stats/users`, { params: { days } }).then(r => r.data),

  getDomainStats: (days?: number, limit?: number) =>
    apiClient.get<DomainStats[]>(`${base}/stats/domains`, { params: { days, limit } }).then(r => r.data),

  triggerAnalysis: () =>
    apiClient.post<{ analyzed: number }>(`${base}/analyze`).then(r => r.data),
};
