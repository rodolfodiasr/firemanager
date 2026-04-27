import type { Device, DeviceCreate } from "../types/device";
import apiClient from "./client";

export const devicesApi = {
  list: () => apiClient.get<Device[]>("/devices").then((r) => r.data),

  get: (id: string) => apiClient.get<Device>(`/devices/${id}`).then((r) => r.data),

  create: (data: DeviceCreate) =>
    apiClient.post<Device>("/devices", data).then((r) => r.data),

  update: (id: string, data: Partial<DeviceCreate>) =>
    apiClient.put<Device>(`/devices/${id}`, data).then((r) => r.data),

  delete: (id: string) => apiClient.delete(`/devices/${id}`),

  healthCheck: (id: string) =>
    apiClient.post<Device>(`/devices/${id}/health-check`).then((r) => r.data),

  inspect: (id: string, resource: "rules" | "nat" | "routes" | "security") =>
    apiClient
      .get<{ resource: string; items: Record<string, unknown>[] }>(`/devices/${id}/inspect`, { params: { resource } })
      .then((r) => r.data),
};
