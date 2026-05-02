import apiClient from "./client";
import type { ServerOperation } from "../types/server_operation";

export const serverOpsApi = {
  getPending: () =>
    apiClient.get<ServerOperation[]>("/server-operations/pending").then((r) => r.data),

  getPendingCount: () =>
    apiClient.get<{ count: number }>("/server-operations/pending/count").then((r) => r.data.count),

  getHistory: () =>
    apiClient.get<ServerOperation[]>("/server-operations/history").then((r) => r.data),

  review: (id: string, body: { approved: boolean; comment: string }) =>
    apiClient.post<{ approved: boolean; status: string; message: string }>(
      `/server-operations/${id}/review`, body
    ).then((r) => r.data),
};
