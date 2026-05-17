import apiClient from "./client";
import type { SecurityPosture } from "../types/executive";

export interface ScheduleReportPayload {
  frequency: "weekly" | "monthly";
  day_of_week: number | null;
  day_of_month: number | null;
  time: string;
  recipients: string[];
}

export const executiveApi = {
  getPosture: () =>
    apiClient.get<SecurityPosture>("/executive/posture").then((r) => r.data),

  downloadReport: (periodDays: number = 30) =>
    apiClient.get("/executive/report/pdf", {
      params: { period_days: periodDays },
      responseType: "blob",
    }).then((r) => r.data as Blob),

  scheduleReport: (payload: ScheduleReportPayload) =>
    apiClient.post("/executive/schedule-report", payload).then((r) => r.data),
};
