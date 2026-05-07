import { apiClient } from "./client";
import type {
  ApplyResponse,
  DivergenceResponse,
  GoldenTemplateCreate,
  GoldenTemplateRead,
  GoldenTemplateSummary,
  GoldenTemplateUpdate,
  GoldenTemplateVersionRead,
  RenderResponse,
} from "../types/goldenTemplate";

export const goldenTemplateApi = {
  list: () =>
    apiClient.get<GoldenTemplateSummary[]>("/golden-templates").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<GoldenTemplateRead>(`/golden-templates/${id}`).then((r) => r.data),

  create: (data: GoldenTemplateCreate) =>
    apiClient.post<GoldenTemplateRead>("/golden-templates", data).then((r) => r.data),

  update: (id: string, data: GoldenTemplateUpdate) =>
    apiClient.put<GoldenTemplateRead>(`/golden-templates/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/golden-templates/${id}`),

  fork: (id: string) =>
    apiClient.post<GoldenTemplateRead>(`/golden-templates/${id}/fork`).then((r) => r.data),

  versions: (id: string) =>
    apiClient.get<GoldenTemplateVersionRead[]>(`/golden-templates/${id}/versions`).then((r) => r.data),

  restoreVersion: (id: string, version: number) =>
    apiClient.post<GoldenTemplateRead>(`/golden-templates/${id}/versions/${version}/restore`).then((r) => r.data),

  render: (id: string, variableValues: Record<string, string>) =>
    apiClient
      .post<RenderResponse>(`/golden-templates/${id}/render`, { variable_values: variableValues })
      .then((r) => r.data),

  prefill: (templateId: string, deviceId: string) =>
    apiClient
      .get<{ variable_values: Record<string, string> }>(`/golden-templates/${templateId}/prefill`, {
        params: { device_id: deviceId },
      })
      .then((r) => r.data),

  divergence: (id: string, deviceId: string, variableValues: Record<string, string>) =>
    apiClient
      .post<DivergenceResponse>(`/golden-templates/${id}/divergence`, {
        device_id: deviceId,
        variable_values: variableValues,
      })
      .then((r) => r.data),

  apply: (id: string, deviceId: string, variableValues: Record<string, string>) =>
    apiClient
      .post<ApplyResponse>(`/golden-templates/${id}/apply`, {
        device_id: deviceId,
        variable_values: variableValues,
      })
      .then((r) => r.data),
};
