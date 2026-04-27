import type { TenantMember, TenantRead, TenantRole } from "../types/tenant";
import apiClient from "./client";

export const tenantsApi = {
  list: () =>
    apiClient.get<TenantRead[]>("/tenants").then((r) => r.data),

  create: (data: { name: string; slug: string }) =>
    apiClient.post<TenantRead>("/tenants", data).then((r) => r.data),

  update: (id: string, data: { name?: string; is_active?: boolean }) =>
    apiClient.patch<TenantRead>(`/tenants/${id}`, data).then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/tenants/${id}`),

  listMembers: (tenantId: string) =>
    apiClient.get<TenantMember[]>(`/tenants/${tenantId}/members`).then((r) => r.data),

  inviteMember: (tenantId: string, data: { user_id: string; role: TenantRole }) =>
    apiClient.post<TenantMember>(`/tenants/${tenantId}/members`, data).then((r) => r.data),

  updateMemberRole: (tenantId: string, userId: string, role: TenantRole) =>
    apiClient.patch<TenantMember>(`/tenants/${tenantId}/members/${userId}`, { role }).then((r) => r.data),

  removeMember: (tenantId: string, userId: string) =>
    apiClient.delete(`/tenants/${tenantId}/members/${userId}`),
};
