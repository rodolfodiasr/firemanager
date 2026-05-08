export type ExternalConnectorType = "guacamole" | "tactical_rmm" | "unifi";

export interface ExternalConnector {
  id: string;
  name: string;
  connector_type: ExternalConnectorType;
  is_active: boolean;
  created_at: string;
}

export interface OnboardingProfileSystem {
  id?: string;
  system_type: string;
  system_id: string | null;
  system_name: string;
  config: Record<string, unknown>;
}

export interface OnboardingProfile {
  id: string;
  name: string;
  description: string | null;
  ad_groups: string[];
  systems: OnboardingProfileSystem[];
  created_at: string;
}

export interface OnboardingActionCreate {
  target_username: string;
  display_name?: string;
  email?: string;
  profile_id: string;
  notes?: string;
}
