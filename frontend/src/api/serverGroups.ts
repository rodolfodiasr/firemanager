import apiClient from "./client";

export interface ServerInGroup {
  id: string;
  name: string;
  host: string;
  os_type: "linux" | "windows";
  is_active: boolean;
}

export interface ServerGroupRead {
  id: string;
  tenant_id: string;
  created_by: string | null;
  name: string;
  description: string | null;
  server_count: number;
  created_at: string;
  updated_at: string;
}

export interface ServerGroupDetail extends ServerGroupRead {
  servers: ServerInGroup[];
}

export interface ServerGroupCreate {
  name: string;
  description?: string;
  server_ids?: string[];
}

export interface ServerGroupUpdate {
  name?: string;
  description?: string;
  server_ids?: string[];
}

export interface GroupAnalyzeResult {
  answer: string;
  sources_used: string[];
  server_count: number;
}

export const serverGroupsApi = {
  list: () =>
    apiClient.get<ServerGroupRead[]>("/server-groups").then((r) => r.data),

  create: (data: ServerGroupCreate) =>
    apiClient.post<ServerGroupDetail>("/server-groups", data).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<ServerGroupDetail>(`/server-groups/${id}`).then((r) => r.data),

  update: (id: string, data: ServerGroupUpdate) =>
    apiClient.put<ServerGroupDetail>(`/server-groups/${id}`, data).then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/server-groups/${id}`),

  analyze: (id: string, question: string) =>
    apiClient
      .post<GroupAnalyzeResult>(`/server-groups/${id}/analyze`, { question })
      .then((r) => r.data),
};
