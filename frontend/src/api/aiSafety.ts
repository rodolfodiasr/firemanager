import apiClient from "./client";

export interface SecurityIncident {
  id: string;
  tenant_id: string;
  title: string;
  description: string | null;
  severity: "critical" | "high" | "medium" | "low";
  category:
    | "unauthorized_access"
    | "data_breach"
    | "malware"
    | "availability"
    | "policy_violation"
    | "other";
  status: "open" | "investigating" | "contained" | "resolved" | "closed";
  reported_by: string | null;
  assigned_to: string | null;
  affected_systems: string[] | null;
  timeline: Array<{
    at: string;
    action: string;
    user_id: string | null;
    details: string;
  }>;
  root_cause: string | null;
  remediation: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceWindow {
  id: string;
  name: string;
  description: string | null;
  starts_at: string;
  ends_at: string;
  recurrence: "once" | "weekly" | "monthly";
  affected_devices: string[] | null;
  block_ai_operations: boolean;
  block_bulk_jobs: boolean;
  is_active: boolean;
  created_at: string;
}

export interface ApprovalRequest {
  id: string;
  tenant_id: string;
  title: string;
  description: string | null;
  risk_level: "critical" | "high" | "medium" | "low";
  operation_context: Record<string, unknown> | null;
  requester_id: string | null;
  requester_note: string | null;
  first_approver_id: string | null;
  first_approved_at: string | null;
  second_approver_id: string | null;
  second_approved_at: string | null;
  rejection_reason: string | null;
  rejected_by: string | null;
  rejected_at: string | null;
  status: "pending_first" | "pending_second" | "approved" | "rejected" | "expired";
  requires_two_approvals: boolean;
  expires_at: string | null;
  created_at: string;
}

export interface ErasureRequest {
  id: string;
  tenant_id: string;
  target_user_email: string;
  reason: string | null;
  legal_basis: string | null;
  status: "pending" | "in_progress" | "completed" | "rejected";
  rejection_reason: string | null;
  affected_tables: string[] | null;
  audit_summary: Record<string, unknown> | null;
  approved_by: string | null;
  approved_at: string | null;
  completed_at: string | null;
  created_at: string;
}

const BASE = "/ai-safety";

export const aiSafetyApi = {
  // Maintenance windows
  listWindows: (activeOnly = false) =>
    apiClient.get<MaintenanceWindow[]>(`${BASE}/maintenance-windows`, { params: { active_only: activeOnly } }).then(r => r.data),
  createWindow: (data: Partial<MaintenanceWindow>) =>
    apiClient.post<MaintenanceWindow>(`${BASE}/maintenance-windows`, data).then(r => r.data),
  updateWindow: (id: string, data: Partial<MaintenanceWindow>) =>
    apiClient.patch<MaintenanceWindow>(`${BASE}/maintenance-windows/${id}`, data).then(r => r.data),
  deleteWindow: (id: string) => apiClient.delete(`${BASE}/maintenance-windows/${id}`),
  getActiveWindow: () =>
    apiClient.get<MaintenanceWindow | null>(`${BASE}/maintenance-windows/active`).then(r => r.data),

  // Approvals
  listApprovals: (status?: string) =>
    apiClient.get<ApprovalRequest[]>(`${BASE}/approvals`, { params: status ? { status } : {} }).then(r => r.data),
  createApproval: (data: {
    title: string; description?: string; risk_level: string;
    operation_context?: Record<string, unknown>; requester_note?: string; requires_two_approvals?: boolean;
  }) => apiClient.post<ApprovalRequest>(`${BASE}/approvals`, data).then(r => r.data),
  approve: (id: string) => apiClient.post<ApprovalRequest>(`${BASE}/approvals/${id}/approve`).then(r => r.data),
  reject: (id: string, reason: string) =>
    apiClient.post<ApprovalRequest>(`${BASE}/approvals/${id}/reject`, { reason }).then(r => r.data),

  // Erasure (LGPD)
  listErasure: (status?: string) =>
    apiClient.get<ErasureRequest[]>(`${BASE}/erasure`, { params: status ? { status } : {} }).then(r => r.data),
  createErasure: (data: { target_user_email: string; reason?: string; legal_basis?: string }) =>
    apiClient.post<ErasureRequest>(`${BASE}/erasure`, data).then(r => r.data),
  approveErasure: (id: string) => apiClient.post<ErasureRequest>(`${BASE}/erasure/${id}/approve`).then(r => r.data),
  executeErasure: (id: string) => apiClient.post<ErasureRequest>(`${BASE}/erasure/${id}/execute`).then(r => r.data),
  rejectErasure: (id: string, reason: string) =>
    apiClient.post<ErasureRequest>(`${BASE}/erasure/${id}/reject`, { reason }).then(r => r.data),

  // Security Incidents (SIRP)
  listIncidents: (params?: { status?: string; severity?: string }) =>
    apiClient
      .get<SecurityIncident[]>(`${BASE}/incidents`, { params })
      .then((r) => r.data),
  createIncident: (data: {
    title: string;
    description?: string;
    severity: string;
    category: string;
    affected_systems?: string[];
  }) => apiClient.post<SecurityIncident>(`${BASE}/incidents`, data).then((r) => r.data),
  updateIncident: (
    id: string,
    data: {
      status?: string;
      assigned_to?: string;
      root_cause?: string;
      remediation?: string;
      resolved_at?: string;
    }
  ) =>
    apiClient.patch<SecurityIncident>(`${BASE}/incidents/${id}`, data).then((r) => r.data),
  addTimeline: (id: string, action: string, details = "") =>
    apiClient
      .post<SecurityIncident>(`${BASE}/incidents/${id}/timeline`, { action, details })
      .then((r) => r.data),
};
