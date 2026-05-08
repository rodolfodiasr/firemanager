import apiClient from "./client";
import type { GoldenBundle, BundleApply } from "../types/golden_bundle";

export const goldenBundlesApi = {
  list: () => apiClient.get<GoldenBundle[]>("/golden-bundles/").then(r => r.data),
  get: (id: string) => apiClient.get<GoldenBundle>(`/golden-bundles/${id}`).then(r => r.data),
  create: (data: Omit<GoldenBundle, "id" | "tenant_id" | "created_at" | "updated_at">) =>
    apiClient.post<GoldenBundle>("/golden-bundles/", data).then(r => r.data),
  update: (id: string, data: Partial<GoldenBundle>) =>
    apiClient.put<GoldenBundle>(`/golden-bundles/${id}`, data).then(r => r.data),
  delete: (id: string) => apiClient.delete(`/golden-bundles/${id}`),
  apply: (id: string, deviceId: string, variables?: Record<string, string>) =>
    apiClient.post<BundleApply>(`/golden-bundles/${id}/apply`, { device_id: deviceId, variables }).then(r => r.data),
  getApply: (applyId: string) => apiClient.get<BundleApply>(`/golden-bundles/applies/${applyId}`).then(r => r.data),
};
