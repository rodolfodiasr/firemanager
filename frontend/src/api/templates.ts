import type { RuleTemplate, TemplateCreate } from "../types/template";
import apiClient from "./client";

export const templatesApi = {
  list: (params?: { vendor?: string; category?: string; firmware?: string }) =>
    apiClient.get<RuleTemplate[]>("/templates", { params }).then((r) => r.data),

  get: (slug: string) =>
    apiClient.get<RuleTemplate>(`/templates/${slug}`).then((r) => r.data),

  create: (body: TemplateCreate) =>
    apiClient.post<RuleTemplate>("/templates", body).then((r) => r.data),

  delete: (slug: string) =>
    apiClient.delete(`/templates/${slug}`),
};
