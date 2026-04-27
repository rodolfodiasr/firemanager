import apiClient from "./client";
import type { DeviceGroup, DeviceGroupCreate, DeviceGroupDetail, DeviceGroupUpdate } from "../types/device_group";
import type { BulkJobDetail } from "../types/bulk_job";

export const deviceGroupsApi = {
  list: () => apiClient.get<DeviceGroup[]>("/device-groups").then((r) => r.data),

  get: (id: string) => apiClient.get<DeviceGroupDetail>(`/device-groups/${id}`).then((r) => r.data),

  create: (payload: DeviceGroupCreate) =>
    apiClient.post<DeviceGroupDetail>("/device-groups", payload).then((r) => r.data),

  update: (id: string, payload: DeviceGroupUpdate) =>
    apiClient.put<DeviceGroupDetail>(`/device-groups/${id}`, payload).then((r) => r.data),

  delete: (id: string) => apiClient.delete(`/device-groups/${id}`),

  createBulkJob: (groupId: string, naturalLanguageInput: string) =>
    apiClient
      .post<BulkJobDetail>(`/device-groups/${groupId}/bulk-job`, {
        natural_language_input: naturalLanguageInput,
      })
      .then((r) => r.data),
};
