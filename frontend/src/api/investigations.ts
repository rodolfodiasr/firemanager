import apiClient from "./client";
const axios = apiClient;

export interface InvestigationPhase {
  id: string;
  phase_number: number;
  phase_name: string;
  phase_purpose: string | null;
  commands: string[];
  raw_output: string | null;
  analysis: string | null;
  findings: string[];
  status: "pending" | "executing" | "done" | "failed";
  executed_at: string | null;
}

export interface InvestigationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  phase_number: number | null;
  created_at: string;
}

export interface InvestigationSession {
  id: string;
  tenant_id: string;
  agent_type: "network" | "firewall" | "n3" | "unified";
  problem_description: string;
  status: "planning" | "active" | "done" | "escalated";
  current_phase: number;
  synthesis: string | null;
  cross_domain_detected: boolean;
  cross_domain_hint: string | null;
  phases: InvestigationPhase[];
  messages: InvestigationMessage[];
  created_at: string;
  updated_at: string;
}

export interface StartInvestigationRequest {
  problem_description: string;
  agent_type: "network" | "firewall" | "n3" | "unified";
  device_id?: string;
  server_id?: string;
  integration_ids?: string[];
}

export const investigationsApi = {
  start: (data: StartInvestigationRequest): Promise<InvestigationSession> =>
    axios.post("/investigations", data).then((r) => r.data),

  list: (agent_type?: string): Promise<InvestigationSession[]> =>
    axios
      .get("/investigations", { params: agent_type ? { agent_type } : undefined })
      .then((r) => r.data),

  get: (id: string): Promise<InvestigationSession> =>
    axios.get(`/investigations/${id}`).then((r) => r.data),

  runPhase: (sessionId: string, phaseNumber: number): Promise<InvestigationSession> =>
    axios.post(`/investigations/${sessionId}/run-phase/${phaseNumber}`).then((r) => r.data),

  sendMessage: (
    sessionId: string,
    message: string
  ): Promise<{ response: string; cross_domain_detected: boolean; cross_domain_hint: string | null }> =>
    axios.post(`/investigations/${sessionId}/message`, { message }).then((r) => r.data),

  synthesize: (sessionId: string): Promise<InvestigationSession> =>
    axios.post(`/investigations/${sessionId}/synthesize`).then((r) => r.data),

  exportRunbook: (sessionId: string): Promise<{ assistant_session_id: string }> =>
    axios.post(`/investigations/${sessionId}/export-runbook`).then((r) => r.data),

  delete: (sessionId: string): Promise<void> =>
    axios.delete(`/investigations/${sessionId}`).then(() => undefined),
};
