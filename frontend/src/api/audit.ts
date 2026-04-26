import type { AuditLog, AuditOperation, AuditPolicy, AuditPolicyUpsert, ReviewRequest, UserForPolicy } from "../types/audit";
import apiClient from "./client";

export const auditApi = {
  getLogs: (params?: { device_id?: string; user_id?: string; skip?: number; limit?: number }) =>
    apiClient.get<AuditLog[]>("/audit/logs", { params }).then((r) => r.data),

  getPending: () =>
    apiClient.get<AuditOperation[]>("/audit/pending").then((r) => r.data),

  getPendingCount: () =>
    apiClient.get<{ count: number }>("/audit/pending/count").then((r) => r.data.count),

  getDirect: () =>
    apiClient.get<AuditOperation[]>("/audit/direct").then((r) => r.data),

  getHistory: () =>
    apiClient.get<AuditOperation[]>("/audit/history").then((r) => r.data),

  review: (operationId: string, body: ReviewRequest) =>
    apiClient
      .post<{ approved: boolean; status: string; message: string }>(
        `/audit/${operationId}/review`,
        body,
      )
      .then((r) => r.data),

  getPolicies: () =>
    apiClient.get<AuditPolicy[]>("/audit/policy").then((r) => r.data),

  upsertPolicy: (body: AuditPolicyUpsert) =>
    apiClient.put<AuditPolicy>("/audit/policy", body).then((r) => r.data),

  deletePolicy: (scopeType: string, scopeId: string, intent: string) =>
    apiClient.delete(`/audit/policy/${scopeType}/${scopeId}/${intent}`),

  getUsers: () =>
    apiClient.get<UserForPolicy[]>("/audit/users").then((r) => r.data),
};
