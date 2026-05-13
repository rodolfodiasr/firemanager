import apiClient from "./client";

export interface PlaybookRule {
  id: string;
  name: string;
  description: string | null;
  trigger_type: string;
  trigger_condition: Record<string, unknown>;
  actions: Array<Record<string, unknown>>;
  cooldown_minutes: number;
  enabled: boolean;
  is_template: boolean;
  template_name: string | null;
  created_at: string;
}

export interface PlaybookCreate {
  name: string;
  description?: string;
  trigger_type: string;
  trigger_condition?: Record<string, unknown>;
  actions?: Array<Record<string, unknown>>;
  cooldown_minutes?: number;
  enabled?: boolean;
}

export interface BuilderState {
  nodes: Array<{ id: string; type: string; position: { x: number; y: number }; data: Record<string, unknown> }>;
  edges: Array<{ id: string; source: string; target: string }>;
}

export interface PlaybookExecution {
  id: string;
  triggered_at: string;
  status: string;
  actions_taken: Array<Record<string, unknown>>;
  resolved_at: string | null;
}

export interface MttrStats {
  by_rule: Array<{ rule_id: string; rule_name: string; avg_minutes: number; execution_count: number }>;
  tenant_avg_minutes: number;
}

export const playbooksApi = {
  list: () =>
    apiClient.get<PlaybookRule[]>("/playbooks").then((r) => r.data),

  create: (data: PlaybookCreate) =>
    apiClient.post<PlaybookRule>("/playbooks", data).then((r) => r.data),

  update: (id: string, data: PlaybookCreate) =>
    apiClient.patch<PlaybookRule>(`/playbooks/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/playbooks/${id}`),

  toggle: (id: string) =>
    apiClient.patch(`/playbooks/${id}/toggle`).then((r) => r.data),

  trigger: (id: string, context?: Record<string, unknown>) =>
    apiClient.post(`/playbooks/${id}/trigger`, context ?? {}).then((r) => r.data),

  seedTemplates: () =>
    apiClient.post<{ seeded: number }>("/playbooks/templates/seed").then((r) => r.data),

  listExecutions: (id: string) =>
    apiClient.get<PlaybookExecution[]>(`/playbooks/${id}/executions`).then((r) => r.data),

  getMttr: () =>
    apiClient.get<MttrStats>("/playbooks/stats/mttr").then((r) => r.data),

  getBuilder: (id: string) =>
    apiClient.get<BuilderState>(`/playbooks/${id}/builder`).then((r) => r.data),

  saveBuilder: (id: string, state: BuilderState) =>
    apiClient.put<{ saved: boolean; nodes: number; edges: number }>(
      `/playbooks/${id}/builder`,
      state
    ).then((r) => r.data),
};
