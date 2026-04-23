import type { AuditLog } from "../types/audit";
import apiClient from "./client";

export const auditApi = {
  getLogs: (params?: { device_id?: string; user_id?: string; skip?: number; limit?: number }) =>
    apiClient.get<AuditLog[]>("/audit/logs", { params }).then((r) => r.data),
};
