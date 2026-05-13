import apiClient from "./client";

export interface SiemConnector {
  id: string;
  name: string;
  siem_type: string;
  base_url: string;
  webhook_secret: string;
  is_active: boolean;
  last_event_at: string | null;
  created_at: string;
}

export interface SiemConnectorCreate {
  name: string;
  siem_type: string;
  base_url: string;
  config?: Record<string, unknown>;
  webhook_secret?: string;
}

export interface SiemAlert {
  id: string;
  connector_id: string;
  source_rule_id: string | null;
  severity: string;
  title: string;
  description: string | null;
  affected_host: string | null;
  source_ip: string | null;
  normalized_at: string;
  playbook_triggered: boolean;
}

export const siemApi = {
  listConnectors: () =>
    apiClient.get<SiemConnector[]>("/siem").then((r) => r.data),

  createConnector: (data: SiemConnectorCreate) =>
    apiClient.post<SiemConnector>("/siem", data).then((r) => r.data),

  getConnector: (id: string) =>
    apiClient.get<SiemConnector>(`/siem/${id}`).then((r) => r.data),

  updateConnector: (id: string, data: SiemConnectorCreate) =>
    apiClient.patch<SiemConnector>(`/siem/${id}`, data).then((r) => r.data),

  deleteConnector: (id: string) =>
    apiClient.delete(`/siem/${id}`),

  listAlerts: (params?: { severity?: string; triggered_only?: boolean; limit?: number }) =>
    apiClient.get<SiemAlert[]>("/siem/alerts/list", { params }).then((r) => r.data),

  ingest: (connectorId: string, payload: Record<string, unknown>) =>
    apiClient.post<{ alert_id: string; severity: string; title: string }>(
      `/siem/${connectorId}/ingest`,
      payload
    ).then((r) => r.data),
};
