import apiClient from "./client";

export type CrossDomainAgentType = "firewall" | "network" | "n3" | "rmm";
export type CrossDomainMode = "consulta" | "diagnostico" | "completo";

export interface CrossDomainSubResult {
  domain: CrossDomainAgentType;
  status: "pending" | "running" | "done" | "error";
  investigation_session_id: string | null;
  synthesis: string | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  rag_docs_found: number;
  rag_doc_titles: string[];
  device_ids: string[];
  mode: CrossDomainMode;
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
  domain_devices?: Record<string, string[]>;
  mode?: CrossDomainMode;
}

export interface SuggestDevicesResponse {
  suggestions: Record<string, Array<{ id: string; name: string; vendor?: string; host?: string; os_type?: string }>>;
}

export interface CorrelateRequest {
  session_id: string;
}

export const crossDomainApi = {
  start: (data: StartCrossDomainRequest): Promise<CrossDomainSession> =>
    apiClient.post("/investigations/cross-domain", data).then((r) => r.data),

  suggestDevices: (problem_description: string): Promise<SuggestDevicesResponse> =>
    apiClient.post("/investigations/cross-domain/suggest-devices", { problem_description }).then((r) => r.data),

  get: (id: string): Promise<CrossDomainSession> =>
    apiClient.get(`/investigations/cross-domain/${id}`).then((r) => r.data),

  list: (): Promise<CrossDomainSession[]> =>
    apiClient.get("/investigations/cross-domain").then((r) => r.data),

  correlate: (id: string): Promise<CrossDomainSession> =>
    apiClient.post(`/investigations/cross-domain/${id}/correlate`).then((r) => r.data),

  rerunDomain: (id: string, domain: CrossDomainAgentType, additionalContext?: string): Promise<CrossDomainSession> =>
    apiClient.post(`/investigations/cross-domain/${id}/rerun/${domain}`, { additional_context: additionalContext ?? null }).then((r) => r.data),

  chat: (id: string, domain: CrossDomainAgentType, message: string): Promise<{ response: string }> =>
    apiClient.post(`/investigations/cross-domain/${id}/chat/${domain}`, { message }).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/investigations/cross-domain/${id}`).then(() => undefined),
};
