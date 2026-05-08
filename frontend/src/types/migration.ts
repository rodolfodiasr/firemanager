export type MigrationStatus =
  | "pending"
  | "analyzing"
  | "ready"
  | "applying"
  | "completed"
  | "failed";

export interface MigrationListItem {
  id: string;
  source_device_id: string;
  target_device_id: string;
  source_vendor: string;
  target_vendor: string;
  status: MigrationStatus;
  ai_level: number;
  created_at: string;
  updated_at: string;
}

export interface ParsedVlan {
  name: string | null;
}

export interface ParsedInterface {
  name: string;
  mode: "trunk" | "access" | "hybrid";
  pvid: string | null;
  tagged_vlans: string[];
  description: string | null;
  port_type: "ethernet" | "fiber" | "lag" | "vlan" | "unknown";
}

export interface L3Interface {
  vlan_id: string;
  ip: string;
  mask: string;
}

export interface MigrationPlan {
  hostname: string | null;
  stp_mode: string | null;
  vlans: Record<string, ParsedVlan>;
  interfaces: ParsedInterface[];
  l3_interfaces: L3Interface[];
  warnings: string[];
}

export interface Migration {
  id: string;
  tenant_id: string;
  source_device_id: string;
  target_device_id: string;
  source_vendor: string;
  target_vendor: string;
  status: MigrationStatus;
  source_config_raw: string | null;
  target_config_raw: string | null;
  migration_plan: MigrationPlan | null;
  port_mapping: Record<string, string> | null;
  commands_preview: string | null;
  warnings: string[] | null;
  error_message: string | null;
  ai_level: number;
  created_at: string;
  updated_at: string;
}

export interface MigrationCreate {
  source_device_id: string;
  target_device_id: string;
  ai_level?: number;
}

export interface PortMappingUpdate {
  port_mapping: Record<string, string>;
}

export interface RegenerateRequest {
  port_mapping?: Record<string, string>;
}

export interface InterfaceAdd {
  name: string;
  target_name: string;
  mode?: string;
  pvid?: string | null;
  tagged_vlans?: string[];
  description?: string | null;
  port_type?: string;
}
