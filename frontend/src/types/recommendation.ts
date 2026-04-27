export interface RuleRow {
  pos: number | null;
  rule_id: string;
  name: string;
  src_zone: string;
  dst_zone: string;
  src: string;
  dst: string;
  service: string;
  action: string;
  enabled: boolean;
  hit_count: number | null;
  shadowed_by?: string;
}

export interface Recommendation {
  id: string;
  severity: "high" | "medium" | "low";
  title: string;
  description: string;
  affected_rules: RuleRow[];
  agent_seed: string;
  manual_hint: string;
  instability_data?: { total_30d: number; total_7d: number };
}

export interface ScoreBreakdown {
  check_id: string;
  title: string;
  severity: "high" | "medium" | "low";
  penalty: number;
}

export interface ScoreData {
  value: number;
  label: string;
  color: string;
  breakdown: ScoreBreakdown[];
}
