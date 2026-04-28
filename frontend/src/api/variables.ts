import type {
  TenantVariable,
  DeviceVariable,
  ResolvedVariable,
  BulkJobPreviewResponse,
  VariableType,
} from "../types/variable";
import apiClient from "./client";

interface VarPayload {
  name: string;
  value: string;
  variable_type: VariableType;
  description?: string;
}

interface VarUpdatePayload {
  value?: string;
  variable_type?: VariableType;
  description?: string;
}

export const variablesApi = {
  // ── Tenant ────────────────────────────────────────────────────────────────
  listTenant: () =>
    apiClient.get<TenantVariable[]>("/variables/tenant").then((r) => r.data),

  createTenant: (data: VarPayload) =>
    apiClient.post<TenantVariable>("/variables/tenant", data).then((r) => r.data),

  updateTenant: (id: string, data: VarUpdatePayload) =>
    apiClient.put<TenantVariable>(`/variables/tenant/${id}`, data).then((r) => r.data),

  deleteTenant: (id: string) =>
    apiClient.delete(`/variables/tenant/${id}`),

  // ── Device ────────────────────────────────────────────────────────────────
  listDevice: (deviceId: string) =>
    apiClient.get<DeviceVariable[]>(`/variables/device/${deviceId}`).then((r) => r.data),

  createDevice: (deviceId: string, data: VarPayload) =>
    apiClient.post<DeviceVariable>(`/variables/device/${deviceId}`, data).then((r) => r.data),

  updateDevice: (deviceId: string, varId: string, data: VarUpdatePayload) =>
    apiClient.put<DeviceVariable>(`/variables/device/${deviceId}/${varId}`, data).then((r) => r.data),

  deleteDevice: (deviceId: string, varId: string) =>
    apiClient.delete(`/variables/device/${deviceId}/${varId}`),

  // ── Effective (merged tenant + device) ───────────────────────────────────
  getEffective: (deviceId: string) =>
    apiClient.get<ResolvedVariable[]>(`/variables/device/${deviceId}/effective`).then((r) => r.data),

  // ── Bulk Preview ─────────────────────────────────────────────────────────
  preview: (data: { device_ids: string[]; natural_language_input: string }) =>
    apiClient.post<BulkJobPreviewResponse>("/bulk-jobs/preview", data).then((r) => r.data),
};
