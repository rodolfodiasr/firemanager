import type {
  ComplianceReport,
  ComplianceReportSummary,
  ComplianceGenerateRequest,
} from "../types/compliance";
import type { RemediationPlan } from "../types/remediation";
import type {
  GovernanceSummary,
  TrustScoreRead,
  FrameworkScoreItem,
  Framework,
} from "../types/governance";
import apiClient from "./client";

export const governanceApi = {
  summary: () =>
    apiClient.get<GovernanceSummary>("/compliance/governance/summary").then((r) => r.data),

  compute: () =>
    apiClient.post<TrustScoreRead[]>("/compliance/governance/compute").then((r) => r.data),

  history: (framework: Framework, limit = 30) =>
    apiClient
      .get<FrameworkScoreItem[]>(`/compliance/governance/history/${framework}`, {
        params: { limit },
      })
      .then((r) => r.data),

  exportExcelUrl: () =>
    `${apiClient.defaults.baseURL}/compliance/governance/export-excel`,
};

export const complianceApi = {
  list: () =>
    apiClient.get<ComplianceReportSummary[]>("/compliance").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<ComplianceReport>(`/compliance/${id}`).then((r) => r.data),

  generate: (data: ComplianceGenerateRequest) =>
    apiClient.post<ComplianceReport>("/compliance", data).then((r) => r.data),

  remediate: (reportId: string, recommendationIndex?: number) =>
    apiClient
      .post<RemediationPlan[]>(`/compliance/${reportId}/remediate`, {
        recommendation_index: recommendationIndex ?? null,
        mode: "recommendations",
      })
      .then((r) => r.data),

  remediateControls: (reportId: string) =>
    apiClient
      .post<RemediationPlan[]>(`/compliance/${reportId}/remediate`, {
        mode: "controls",
      })
      .then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/compliance/${id}`),

  exportPdfUrl: (id: string) =>
    `${apiClient.defaults.baseURL}/compliance/${id}/export-pdf`,
};
