export type ApplyStrategy = "cli_ssh" | "rest_api" | "manual_only";
export type BundleStatus = "draft" | "applying" | "applied" | "failed" | "rolled_back";
export type SectionType = "base_config" | "objects" | "access_rules" | "content_filter" | "geo_ip" | "vpn" | "sd_wan";

export interface BundleSection {
  id: string;
  bundle_id: string;
  section_type: SectionType;
  template_id: string | null;
  rest_payload_template: string | null;
  apply_strategy: ApplyStrategy;
  apply_order: number;
  rollback_strategy: string;
}

export interface GoldenBundle {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  vendor: string;
  variables: Record<string, string>;
  sections: BundleSection[];
  created_at: string;
  updated_at: string;
}

export interface BundleApply {
  id: string;
  bundle_id: string;
  device_id: string;
  status: BundleStatus;
  variables_used: Record<string, string> | null;
  section_results: Record<string, { status: string; result?: unknown; error?: string }> | null;
  started_at: string;
  completed_at: string | null;
}
