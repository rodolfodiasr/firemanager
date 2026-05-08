import apiClient from "./client";
import type { TenantBranding, ApiKey, ApiKeyCreate, ApiKeyCreated } from "../types/enterprise";

export const enterpriseApi = {
  getBranding: () => apiClient.get<TenantBranding>("/enterprise/branding").then(r => r.data),
  updateBranding: (data: Partial<TenantBranding>) => apiClient.put<TenantBranding>("/enterprise/branding", data).then(r => r.data),
  listApiKeys: () => apiClient.get<ApiKey[]>("/enterprise/api-keys").then(r => r.data),
  createApiKey: (data: ApiKeyCreate) => apiClient.post<ApiKeyCreated>("/enterprise/api-keys", data).then(r => r.data),
  deleteApiKey: (id: string) => apiClient.delete(`/enterprise/api-keys/${id}`),
  rotateApiKey: (id: string) => apiClient.post<ApiKeyCreated>(`/enterprise/api-keys/${id}/rotate`).then(r => r.data),
};
