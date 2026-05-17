import apiClient from "./client";

export type CrossDomainAgentType = "firewall" | "network" | "n3" | "rmm";

export interface CrossDomainSubResult {
  domain: CrossDomainAgentType;
  status: "pending" | "running" | "done" | "error";
  investigation_session_id: string | null;
  synthesis: string | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface CrossDomainSession {
  id: string;
  tenant_id: string;
  problem_description: string;
  domains: CrossDomainAgentType[];
  status: "running" | "done" | "partial";
  correlation: string | null;
  sub_results: CrossDomainSubResult[];
  created_at: string;
  updated_at: string;
}

export interface StartCrossDomainRequest {
  problem_description: string;
  domains: CrossDomainAgentType[];
  device_ids?: string[];
  server_ids?: string[];
  integration_ids?: string[];
  rmm_integration_id?: string;
}

export interface CorrelateRequest {
  session_id: string;
}

export const crossDomainApi = {
  start: (data: StartCrossDomainRequest): Promise<CrossDomainSession> =>
    apiClient.post("/investigations/cross-domain", data).then((r) => r.data),

  get: (id: string): Promise<CrossDomainSession> =>
    apiClient.get(`/investigations/cross-domain/${id}`).then((r) => r.data),

  list: (): Promise<CrossDomainSession[]> =>
    apiClient.get("/investigations/cross-domain").then((r) => r.data),

  correlate: (id: string): Promise<CrossDomainSession> =>
    apiClient.post(`/investigations/cross-domain/${id}/correlate`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/investigations/cross-domain/${id}`).then(() => undefined),
};
