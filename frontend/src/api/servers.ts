import type { Server, ServerCreate, ServerUpdate, AnalyzeRequest, AnalyzeResponse } from "../types/server";
import apiClient from "./client";

export const serversApi = {
  list: () =>
    apiClient.get<Server[]>("/servers").then((r) => r.data),

  create: (data: ServerCreate) =>
    apiClient.post<Server>("/servers", data).then((r) => r.data),

  update: (id: string, data: ServerUpdate) =>
    apiClient.patch<Server>(`/servers/${id}`, data).then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/servers/${id}`),

  test: (id: string) =>
    apiClient.post<{ success: boolean; message: string }>(`/servers/${id}/test`).then((r) => r.data),

  analyze: (data: AnalyzeRequest) =>
    apiClient.post<AnalyzeResponse>("/servers/analyze", data).then((r) => r.data),
};
