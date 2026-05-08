import apiClient from "./client";
import type { SecurityPosture } from "../types/executive";

export const executiveApi = {
  getPosture: () =>
    apiClient.get<SecurityPosture>("/executive/posture").then((r) => r.data),

  downloadReport: (periodDays: number = 30) =>
    apiClient.get("/executive/report/pdf", {
      params: { period_days: periodDays },
      responseType: "blob",
    }).then((r) => r.data as Blob),
};
