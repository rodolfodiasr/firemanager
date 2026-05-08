import apiClient from "./client";
import type {
  AuditReport,
  AuditSummary,
  DatabaseConnector,
  TestResult,
} from "../types/database";

export interface ConnectorPayload {
  name: string;
  description?: string;
  db_type: string;
  host: string;
  port?: number;
  database_name: string;
  server_id?: string;
  credentials: { username: string; password: string; ssl?: boolean };
}

export const databaseApi = {
  list: () =>
    apiClient.get<DatabaseConnector[]>("/database-connectors").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<DatabaseConnector>(`/database-connectors/${id}`).then((r) => r.data),

  create: (data: ConnectorPayload) =>
    apiClient.post<DatabaseConnector>("/database-connectors", data).then((r) => r.data),

  update: (id: string, data: Partial<ConnectorPayload>) =>
    apiClient.patch<DatabaseConnector>(`/database-connectors/${id}`, data).then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/database-connectors/${id}`),

  test: (id: string) =>
    apiClient.post<TestResult>(`/database-connectors/${id}/test`).then((r) => r.data),

  runAudit: (id: string) =>
    apiClient.post<AuditReport>(`/database-connectors/${id}/audit`).then((r) => r.data),

  listAudits: (id: string) =>
    apiClient.get<AuditSummary[]>(`/database-connectors/${id}/audits`).then((r) => r.data),

  getAudit: (connectorId: string, auditId: string) =>
    apiClient
      .get<AuditReport>(`/database-connectors/${connectorId}/audits/${auditId}`)
      .then((r) => r.data),
};
