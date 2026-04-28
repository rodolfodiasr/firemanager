import type {
  Server, ServerCreate, ServerUpdate,
  AnalyzeRequest, AnalyzeResponse, AnalysisSession,
} from "../types/server";
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

  listSessions: (limit = 50) =>
    apiClient.get<AnalysisSession[]>("/servers/sessions", { params: { limit } }).then((r) => r.data),

  deleteSession: (id: string) =>
    apiClient.delete(`/servers/sessions/${id}`),

  exportSessionPdfUrl: (id: string) =>
    `${apiClient.defaults.baseURL}/servers/sessions/${id}/export-pdf`,
};
