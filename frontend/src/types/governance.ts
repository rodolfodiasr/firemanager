export type Framework = "cis_benchmark" | "nist_csf" | "iso_27001" | "eternity";

export interface TrustScoreRead {
  id: string;
  tenant_id: string;
  framework: Framework;
  score_pct: number;
  breakdown: Record<string, unknown>;
  narrative: string;
  computed_at: string;
}

export interface FrameworkScoreItem {
  framework: Framework;
  score_pct: number;
  computed_at: string;
}

export interface GovernanceSummary {
  eternity_score: number | null;
  cis_score: number | null;
  nist_score: number | null;
  iso_score: number | null;
  narrative: string;
  computed_at: string | null;
  scores: TrustScoreRead[];
}

// Eternity Trust Score breakdown
export interface EternityBreakdown {
  components: Record<string, number>;
  weights: Record<string, number>;
  details: Record<string, Record<string, unknown>>;
}

// NIST CSF breakdown — values are null when no CIS controls mapped to that function
export interface WazuhDetectData {
  score: number;
  agent_coverage: number;
  alert_posture: number;
  total_agents: number;
  active_agents: number;
  disconnected_agents: number;
  critical_alerts_30d: number;
}

export interface NistBreakdown {
  nist_functions: Record<string, number | null>;
  nist_labels: Record<string, string>;
  source: string;
  wazuh_detect: WazuhDetectData | null;
  server_count: number;
  total_controls: number;
  methodology: string;
}

// ISO 27001:2022 breakdown — values are null when no CIS controls mapped to that domain
export interface IsoBreakdown {
  iso_domains: Record<string, number | null>;
  iso_labels: Record<string, string>;
  source: string;
  server_count: number;
  total_controls: number;
  mfa_adoption: {
    score: number | null;
    mfa_enabled: number;
    total_users: number;
  };
  methodology: string;
}
