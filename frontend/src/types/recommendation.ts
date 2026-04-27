export interface Recommendation {
  id: string;
  severity: "high" | "medium" | "low";
  title: string;
  description: string;
  affected_rules: string[];
  agent_seed: string;
  manual_hint: string;
  hit_counts?: Record<string, number | null>;
}
