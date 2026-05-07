import apiClient from "./client";
import type {
  ConnectivityAnalysisRead,
  ConnectivityAnalysisSummary,
} from "../types/connectivity";

export const connectivityApi = {
  trigger: (deviceId: string) =>
    apiClient
      .post<ConnectivityAnalysisSummary>(`/connectivity/analyze/${deviceId}`)
      .then((r) => r.data),

  list: () =>
    apiClient
      .get<ConnectivityAnalysisSummary[]>("/connectivity")
      .then((r) => r.data),

  listByDevice: (deviceId: string) =>
    apiClient
      .get<ConnectivityAnalysisSummary[]>(`/connectivity/device/${deviceId}`)
      .then((r) => r.data),

  get: (id: string) =>
    apiClient
      .get<ConnectivityAnalysisRead>(`/connectivity/${id}`)
      .then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/connectivity/${id}`),
};
