import apiClient from "./client";
import type {
  IdentityProvider,
  IdentityUser,
  LifecycleAction,
  OrphanUser,
} from "../types/identity";

export const identityApi = {
  // Providers
  listProviders: () =>
    apiClient.get<IdentityProvider[]>("/identity/providers").then((r) => r.data),

  createProvider: (data: { name: string; provider_type: string; config: Record<string, unknown> }) =>
    apiClient.post<IdentityProvider>("/identity/providers", data).then((r) => r.data),

  deleteProvider: (id: string) =>
    apiClient.delete(`/identity/providers/${id}`),

  syncProvider: (id: string) =>
    apiClient.post<IdentityProvider>(`/identity/providers/${id}/sync`).then((r) => r.data),

  listUsers: (providerId: string) =>
    apiClient.get<IdentityUser[]>(`/identity/providers/${providerId}/users`).then((r) => r.data),

  // Lifecycle actions
  listActions: () =>
    apiClient.get<LifecycleAction[]>("/identity/actions").then((r) => r.data),

  createAction: (data: {
    target_username: string;
    display_name?: string;
    email?: string;
    notes?: string;
  }) =>
    apiClient.post<LifecycleAction>("/identity/actions", data).then((r) => r.data),

  getAction: (id: string) =>
    apiClient.get<LifecycleAction>(`/identity/actions/${id}`).then((r) => r.data),

  approveAction: (id: string) =>
    apiClient.post(`/identity/actions/${id}/approve`).then((r) => r.data),

  cancelAction: (id: string) =>
    apiClient.post(`/identity/actions/${id}/cancel`).then((r) => r.data),

  // Orphan accounts
  listOrphans: () =>
    apiClient.get<OrphanUser[]>("/identity/orphans").then((r) => r.data),
};
