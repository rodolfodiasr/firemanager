import apiClient from "./client";
import type { KnowledgeDocument, KnowledgeStats, SearchResult } from "../types/knowledge";

export const knowledgeApi = {
  upload: (file: File, name?: string, description?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (name) form.append("name", name);
    if (description) form.append("description", description);
    return apiClient
      .post<KnowledgeDocument>("/knowledge/documents", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  list: () =>
    apiClient.get<KnowledgeDocument[]>("/knowledge/documents").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<KnowledgeDocument>(`/knowledge/documents/${id}`).then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/knowledge/documents/${id}`),

  reindex: (id: string) =>
    apiClient.post<KnowledgeDocument>(`/knowledge/documents/${id}/reindex`).then((r) => r.data),

  toggleActive: (id: string, is_active: boolean) =>
    apiClient.patch<KnowledgeDocument>(`/knowledge/documents/${id}/active`, { is_active }).then((r) => r.data),

  search: (q: string) =>
    apiClient.get<SearchResult>("/knowledge/documents/search/test", { params: { q } }).then((r) => r.data),

  stats: () =>
    apiClient.get<KnowledgeStats>("/knowledge/documents/stats/summary").then((r) => r.data),
};
