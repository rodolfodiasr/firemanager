import apiClient from "./client";

export interface CompliancePack {
  id: string;
  name: string;
  framework: string;
  version: string | null;
  description: string | null;
  is_builtin: boolean;
  control_count: number;
}

export interface PackControl {
  id: string;
  control_id: string;
  title: string;
  category: string | null;
  severity: string;
  verification_type: string;
  evidence_hint: string | null;
  sort_order: number;
}

export interface PackDetail extends CompliancePack {
  controls: PackControl[];
}

export interface AssessmentFinding {
  control_id: string;
  title: string;
  category: string | null;
  severity: string;
  status: "not_evaluated" | "compliant" | "partial" | "non_compliant";
  evidence: string;
  notes: string;
}

export interface Assessment {
  id: string;
  tenant_id: string;
  pack_id: string | null;
  pack_name: string;
  name: string;
  status: "in_progress" | "completed";
  overall_score: number | null;
  compliant_count: number;
  partial_count: number;
  non_compliant_count: number;
  total_controls: number;
  findings: AssessmentFinding[] | null;
  started_at: string;
  completed_at: string | null;
}

export interface BcdrPlan {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  rto_hours: number;
  rpo_hours: number;
  scope: string | null;
  contacts: { name: string; role: string; phone: string; email: string }[] | null;
  recovery_steps: { step: string; owner: string; duration_minutes: number }[] | null;
  last_test_at: string | null;
  last_test_result: "passed" | "failed" | "partial" | null;
  last_test_notes: string | null;
  status: "draft" | "active" | "archived";
  created_at: string;
  updated_at: string;
}

export interface SlaConfig {
  id: string;
  tier_name: string;
  response_minutes: number;
  resolution_hours: number;
  escalation_hours: number | null;
  is_active: boolean;
}

const BASE = "/compliance-enterprise";

export const complianceEnterpriseApi = {
  // Packs
  listPacks: () => apiClient.get<CompliancePack[]>(`${BASE}/packs`).then(r => r.data),
  getPack: (id: string) => apiClient.get<PackDetail>(`${BASE}/packs/${id}`).then(r => r.data),
  seedPacks: () => apiClient.post(`${BASE}/packs/seed`).then(r => r.data),

  // Assessments
  listAssessments: () => apiClient.get<Assessment[]>(`${BASE}/assessments`).then(r => r.data),
  getAssessment: (id: string) => apiClient.get<Assessment>(`${BASE}/assessments/${id}`).then(r => r.data),
  createAssessment: (pack_id: string, name: string) =>
    apiClient.post<Assessment>(`${BASE}/assessments`, { pack_id, name }).then(r => r.data),
  updateFinding: (assessmentId: string, finding: { control_id: string; status: string; evidence: string; notes: string }) =>
    apiClient.patch<Assessment>(`${BASE}/assessments/${assessmentId}/finding`, finding).then(r => r.data),
  completeAssessment: (id: string) =>
    apiClient.post<Assessment>(`${BASE}/assessments/${id}/complete`).then(r => r.data),

  // BC/DR
  listBcdr: () => apiClient.get<BcdrPlan[]>(`${BASE}/bcdr`).then(r => r.data),
  createBcdr: (data: Partial<BcdrPlan>) => apiClient.post<BcdrPlan>(`${BASE}/bcdr`, data).then(r => r.data),
  updateBcdr: (id: string, data: Partial<BcdrPlan>) =>
    apiClient.patch<BcdrPlan>(`${BASE}/bcdr/${id}`, data).then(r => r.data),
  deleteBcdr: (id: string) => apiClient.delete(`${BASE}/bcdr/${id}`),
  recordTest: (id: string, result: string, notes: string) =>
    apiClient.post<BcdrPlan>(`${BASE}/bcdr/${id}/test`, { result, notes }).then(r => r.data),

  // SLA
  getSla: () => apiClient.get<SlaConfig[]>(`${BASE}/sla`).then(r => r.data),
  seedSla: () => apiClient.post(`${BASE}/sla/seed`).then(r => r.data),
  upsertSla: (tier: string, data: Partial<SlaConfig>) =>
    apiClient.put<SlaConfig>(`${BASE}/sla/${tier}`, data).then(r => r.data),
};
