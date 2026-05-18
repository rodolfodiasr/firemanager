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

  submitFindings: (compositeId: string, subId: string, data: SubmitFindingsRequest): Promise<SubInvestigation> =>
    apiClient.post(`/investigations/composite/${compositeId}/sub/${subId}/submit`, data).then((r) => r.data),

  escalate: (compositeId: string, subId: string): Promise<SubInvestigation> =>
    apiClient.post(`/investigations/composite/${compositeId}/sub/${subId}/escalate`).then((r) => r.data),

  reopen: (compositeId: string, subId: string): Promise<SubInvestigation> =>
    apiClient.post(`/investigations/composite/${compositeId}/sub/${subId}/reopen`).then((r) => r.data),

  consolidate: (id: string): Promise<CompositeInvestigation> =>
    apiClient.post(`/investigations/composite/${id}/consolidate`).then((r) => r.data),

  generateActionPlan: (id: string): Promise<CompositeInvestigation> =>
    apiClient.post(`/investigations/composite/${id}/action-plan`).then((r) => r.data),

  resolve: (id: string): Promise<CompositeInvestigation> =>
    apiClient.post(`/investigations/composite/${id}/resolve`).then((r) => r.data),

  chat: (id: string, message: string): Promise<{ response: string }> =>
    apiClient.post(`/investigations/composite/${id}/chat`, { message }).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/investigations/composite/${id}`).then(() => undefined),

  mySubInvestigations: (): Promise<SubInvestigation[]> =>
    apiClient.get("/investigations/composite/my-sub-investigations").then((r) => r.data),
};
