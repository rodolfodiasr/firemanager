import apiClient from "./client";

export interface AgentInGroup {
  id: string;
  hostname: string;
  os_name: string | null;
  ip_address: string | null;
  status: string;
}

export interface RmmGroupRead {
  id: string;
  tenant_id: string;
  created_by: string | null;
  name: string;
  description: string | null;
  agent_count: number;
  created_at: string;
  updated_at: string;
}

export interface RmmGroupDetail extends RmmGroupRead {
  agents: AgentInGroup[];
}

export interface RmmGroupCreate {
  name: string;
  description?: string;
  agent_ids?: string[];
}

export interface RmmGroupUpdate {
  name?: string;
  description?: string;
  agent_ids?: string[];
}

export interface BulkRunRequest {
  shell?: string;
  run_type?: "command" | "script";
  body: string;
  timeout?: number;
}

export interface BulkRunAgentResult {
  agent_id: string;
  hostname: string;
  status: "ok" | "error" | "skipped";
  output: string;
  exit_code?: number;
}

export interface BulkRunResult {
  group_name: string;
  agent_count: number;
  results: BulkRunAgentResult[];
}

export const rmmGroupsApi = {
  list: () =>
    apiClient.get<RmmGroupRead[]>("/rmm/groups").then((r) => r.data),

  create: (data: RmmGroupCreate) =>
    apiClient.post<RmmGroupDetail>("/rmm/groups", data).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<RmmGroupDetail>(`/rmm/groups/${id}`).then((r) => r.data),

  update: (id: string, data: RmmGroupUpdate) =>
    apiClient.put<RmmGroupDetail>(`/rmm/groups/${id}`, data).then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/rmm/groups/${id}`),

  bulkRun: (id: string, data: BulkRunRequest) =>
    apiClient.post<BulkRunResult>(`/rmm/groups/${id}/run`, data).then((r) => r.data),
};
