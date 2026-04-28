export type ComplianceSource = "wazuh" | "ssh";

export interface ComplianceControl {
  control_id: string;
  title: string;
  description: string;
  result: "passed" | "failed" | "not_applicable";
  risk_level: "critical" | "high" | "medium" | "low";
  remediation: string;
  rationale?: string;
  references?: string;
}

export interface ComplianceRecommendation {
  priority: number;
  title: string;
  description: string;
  remediation_steps: string;
}

export interface ComplianceReportSummary {
  id: string;
  tenant_id: string;
  server_id: string;
  source: ComplianceSource;
  policy_name: string;
  score_pct: number;
  total_checks: number;
  passed: number;
  failed: number;
  not_applicable: number;
  created_at: string;
}

export interface ComplianceReport extends ComplianceReportSummary {
  agent_id: string | null;
  policy_id: string | null;
  controls: ComplianceControl[];
  ai_summary: string;
  ai_recommendations: ComplianceRecommendation[];
}

export interface ComplianceGenerateRequest {
  server_id: string;
  policy_id?: string;
  force_source?: "wazuh" | "ssh";
}
