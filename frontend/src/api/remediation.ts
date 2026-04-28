import type { RemediationPlan, RemediationRequest } from "../types/remediation";
import apiClient from "./client";

export const remediationApi = {
  list: () =>
    apiClient.get<RemediationPlan[]>("/remediation").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<RemediationPlan>(`/remediation/${id}`).then((r) => r.data),

  create: (data: RemediationRequest) =>
    apiClient.post<RemediationPlan>("/remediation", data).then((r) => r.data),

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

  remove: (id: string) =>
    apiClient.delete(`/remediation/${id}`),
};
