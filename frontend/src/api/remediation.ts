import type {
  RemediationCampaign,
  RemediationCommand,
  RemediationContextRequest,
  RemediationPlan,
  RemediationRequest,
  RemediationTemplate,
} from "../types/remediation";
import apiClient from "./client";

export const remediationApi = {
  list: () =>
    apiClient.get<RemediationPlan[]>("/remediation").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<RemediationPlan>(`/remediation/${id}`).then((r) => r.data),

  create: (data: RemediationRequest) =>
    apiClient.post<RemediationPlan>("/remediation", data).then((r) => r.data),

  createFromContext: (data: RemediationContextRequest) =>
    apiClient.post<RemediationPlan>("/remediation/context", data).then((r) => r.data),

  createFromAlert: (eventId: string) =>
    apiClient.post<RemediationPlan>(`/alerts/events/${eventId}/remediate`).then((r) => r.data),

  listTemplates: () =>
    apiClient.get<RemediationTemplate[]>("/remediation/templates").then((r) => r.data),

  createTemplate: (data: { name: string; description?: string; vendor?: string; category?: string; commands?: object[] }) =>
    apiClient.post<RemediationTemplate>("/remediation/templates", data).then((r) => r.data),

  deleteTemplate: (id: string) =>
    apiClient.delete(`/remediation/templates/${id}`),

  listCampaigns: () =>
    apiClient.get<RemediationCampaign[]>("/remediation/campaigns").then((r) => r.data),

  createCampaign: (data: { name: string; template_id?: string; origin_type?: string; origin_ref?: string }) =>
    apiClient.post<RemediationCampaign>("/remediation/campaigns", data).then((r) => r.data),

  updateCampaignStatus: (id: string, status: string) =>
    apiClient.patch(`/remediation/campaigns/${id}/status`, { status }).then((r) => r.data),

  updateCommand: (planId: string, commandId: string, data: { command: string; description?: string }) =>
    apiClient
      .patch<RemediationCommand>(`/remediation/${planId}/commands/${commandId}`, data)
      .then((r) => r.data),

  approveCommand: (planId: string, commandId: string) =>
    apiClient
      .post<{ id: string; status: string }>(`/remediation/${planId}/commands/${commandId}/approve`)
      .then((r) => r.data),

  rejectCommand: (planId: string, commandId: string, comment?: string) =>
    apiClient
      .post<{ id: string; status: string }>(`/remediation/${planId}/commands/${commandId}/reject`, { comment })
      .then((r) => r.data),

  execute: (planId: string) =>
    apiClient.post<RemediationPlan>(`/remediation/${planId}/execute`).then((r) => r.data),

  retry: (planId: string) =>
    apiClient.post<RemediationPlan>(`/remediation/${planId}/retry`).then((r) => r.data),

  corrective: (planId: string, observation: string) =>
    apiClient
      .post<RemediationPlan>(`/remediation/${planId}/corrective`, { observation })
      .then((r) => r.data),

  createRollback: (planId: string) =>
    apiClient
      .post<RemediationPlan>(`/remediation/${planId}/rollback`)
      .then((r) => r.data),

  exportPdf: async (planId: string) => {
    const token = localStorage.getItem("access_token");
    const res = await fetch(`/api/remediation/${planId}/export`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error("Erro ao gerar PDF");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `remediation_${planId.slice(0, 8)}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  },

  remove: (id: string) =>
    apiClient.delete(`/remediation/${id}`),
};
