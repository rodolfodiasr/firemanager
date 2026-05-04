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

// breakdown shapes per framework
export interface EternityBreakdown {
  components: Record<string, number>;
  weights: Record<string, number>;
}

export interface NistBreakdown {
  nist_functions: Record<string, number>;
}

export interface IsoBreakdown {
  iso_controls: Record<string, number>;
}
