import apiClient from "./client";
import type { AlertChannel, AlertRule, AlertEvent } from "../types/alerts";

export const alertsApi = {
  listChannels: () =>
    apiClient.get<AlertChannel[]>("/alerts/channels").then((r) => r.data),

  createChannel: (data: { name: string; channel_type: string; config: Record<string, unknown> }) =>
    apiClient.post<AlertChannel>("/alerts/channels", data).then((r) => r.data),

  deleteChannel: (id: string) =>
    apiClient.delete(`/alerts/channels/${id}`),

  testChannel: (id: string) =>
    apiClient.post<{ success: boolean; message: string }>(`/alerts/channels/${id}/test`).then((r) => r.data),

  listRules: () =>
    apiClient.get<AlertRule[]>("/alerts/rules").then((r) => r.data),

  createRule: (data: { name: string; trigger: string; severity: string; channel_ids: string[] }) =>
    apiClient.post<AlertRule>("/alerts/rules", data).then((r) => r.data),

  updateRule: (id: string, data: { name: string; trigger: string; severity: string; channel_ids: string[] }) =>
    apiClient.put<AlertRule>(`/alerts/rules/${id}`, data).then((r) => r.data),

  toggleRule: (id: string) =>
    apiClient.patch(`/alerts/rules/${id}/toggle`).then((r) => r.data),

  deleteRule: (id: string) =>
    apiClient.delete(`/alerts/rules/${id}`),

  listEvents: () =>
    apiClient.get<AlertEvent[]>("/alerts/events").then((r) => r.data),
};
