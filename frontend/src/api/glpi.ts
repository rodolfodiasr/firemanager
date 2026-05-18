import type {
  GlpiIntegration,
  GlpiIntegrationCreate,
  GlpiIntegrationUpdate,
  GlpiTestResult,
  GlpiAnalysisListItem,
  GlpiTicketAnalysis,
  GlpiKrDraft,
} from "../types/glpi";
import apiClient from "./client";

export const glpiApi = {
  // Integration
  getIntegration: () =>
    apiClient.get<GlpiIntegration | null>("/glpi/integrations").then((r) => r.data),

  createIntegration: (data: GlpiIntegrationCreate) =>
    apiClient.post<GlpiIntegration>("/glpi/integrations", data).then((r) => r.data),

  updateIntegration: (id: string, data: GlpiIntegrationUpdate) =>
    apiClient.patch<GlpiIntegration>(`/glpi/integrations/${id}`, data).then((r) => r.data),

  deleteIntegration: (id: string) =>
    apiClient.delete(`/glpi/integrations/${id}`),

  testIntegration: (id: string) =>
    apiClient.post<GlpiTestResult>(`/glpi/integrations/${id}/test`).then((r) => r.data),

  triggerSync: (id: string) =>
    apiClient.post(`/glpi/integrations/${id}/sync`).then((r) => r.data),

  // Analyses
  listAnalyses: (params?: {
    status?: string;
    security_only?: boolean;
    recurrent_only?: boolean;
    itemtype?: string;
    skip?: number;
    limit?: number;
    include_cancelled?: boolean;
  }) =>
    apiClient
      .get<GlpiAnalysisListItem[]>("/glpi/analyses", { params })
      .then((r) => r.data),

  getAnalysis: (id: string) =>
    apiClient.get<GlpiTicketAnalysis>(`/glpi/analyses/${id}`).then((r) => r.data),

  runAnalysis: (id: string, deviceIds: string[]) =>
    apiClient.post(`/glpi/analyses/${id}/run`, { device_ids: deviceIds }).then((r) => r.data),

  openChatFromGlpi: (analysisId: string) =>
    apiClient
      .post<{ session_id: string }>(`/glpi/analyses/${analysisId}/open-chat`)
      .then((r) => r.data),

  // KR loop
  listKrDrafts: () =>
    apiClient.get<GlpiKrDraft[]>("/glpi/kr-drafts").then((r) => r.data),

  resolveKr: (analysisId: string, params: { book_id?: number; chapter_id?: number } = {}) =>
    apiClient
      .post<{ published: boolean; bookstack_page_url: string | null; followup_posted: boolean; kr_closed: boolean }>(
        `/glpi/analyses/${analysisId}/resolve-kr`,
        params,
      )
      .then((r) => r.data),

  // BookStack structure
  listBookstackBooks: () =>
    apiClient.get<{ id: number; name: string; slug: string }[]>("/glpi/bookstack/books").then((r) => r.data),

  listBookstackChapters: (bookId: number) =>
    apiClient.get<{ id: number; name: string; book_id: number }[]>(`/glpi/bookstack/books/${bookId}/chapters`).then((r) => r.data),
};
