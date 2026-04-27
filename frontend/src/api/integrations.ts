import type { Integration, IntegrationCreate, IntegrationUpdate, TestResult } from "../types/integration";
import apiClient from "./client";

export const integrationsApi = {
  list: () =>
    apiClient.get<Integration[]>("/integrations").then((r) => r.data),

  create: (data: IntegrationCreate) =>
    apiClient.post<Integration>("/integrations", data).then((r) => r.data),

  update: (id: string, data: IntegrationUpdate) =>
    apiClient.patch<Integration>(`/integrations/${id}`, data).then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/integrations/${id}`),

  test: (id: string) =>
    apiClient.post<TestResult>(`/integrations/${id}/test`).then((r) => r.data),
};
