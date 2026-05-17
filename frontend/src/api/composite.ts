import apiClient from "./client";

export type CompositeDomain = "firewall" | "network" | "n3" | "rmm";
export type SubInvestigationStatus = "pending" | "assigned" | "in_progress" | "submitted" | "escalated";
export type CompositeStatus = "draft" | "active" | "consolidating" | "resolved";

export interface SubInvestigation {
  id: string;
  composite_id: string;
  domain: CompositeDomain;
  assigned_to_id: string | null;
  assigned_to_name: string | null;
  status: SubInvestigationStatus;
  findings: string | null;
  investigation_session_id: string | null;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompositeInvestigation {
  id: string;
  tenant_id: string;
  symptom: string;
  created_by_id: string;
  created_by_name: string;
  status: CompositeStatus;
  domains: CompositeDomain[];
  sub_investigations: SubInvestigation[];
  consolidation: string | null;
  action_plan_session_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateCompositeRequest {
  symptom: string;
  domains: CompositeDomain[];
}

export interface SubmitFindingsRequest {
  findings: string;
  investigation_session_id?: string;
}

export const compositeApi = {
  create: (data: CreateCompositeRequest): Promise<CompositeInvestigation> =>
    apiClient.post("/investigations/composite", data).then((r) => r.data),

  list: (): Promise<CompositeInvestigation[]> =>
    apiClient.get("/investigations/composite").then((r) => r.data),

  get: (id: string): Promise<CompositeInvestigation> =>
    apiClient.get(`/investigations/composite/${id}`).then((r) => r.data),

  // Submete os findings de um sub-domínio
  submitFindings: (compositeId: string, subId: string, data: SubmitFindingsRequest): Promise<SubInvestigation> =>
    apiClient.put(`/investigations/composite/${compositeId}/sub/${subId}/submit`, data).then((r) => r.data),

  // Escala o sub-domínio (especialista pede ajuda)
  escalate: (compositeId: string, subId: string, reason: string): Promise<SubInvestigation> =>
    apiClient.put(`/investigations/composite/${compositeId}/sub/${subId}/escalate`, { reason }).then((r) => r.data),

  // N3 consolida todos os findings com IA
  consolidate: (id: string): Promise<CompositeInvestigation> =>
    apiClient.post(`/investigations/composite/${id}/consolidate`).then((r) => r.data),

  // Gera plano de ação no Assistente IA a partir da consolidação
  generateActionPlan: (id: string): Promise<{ assistant_session_id: string }> =>
    apiClient.post(`/investigations/composite/${id}/action-plan`).then((r) => r.data),

  resolve: (id: string): Promise<CompositeInvestigation> =>
    apiClient.post(`/investigations/composite/${id}/resolve`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/investigations/composite/${id}`).then(() => undefined),

  // Lista sub-investigações atribuídas ao usuário atual
  mySubInvestigations: (): Promise<(SubInvestigation & { composite_symptom: string })[]> =>
    apiClient.get("/investigations/composite/my-tasks").then((r) => r.data),
};
