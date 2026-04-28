export type VariableType =
  | "string"
  | "network"
  | "ip"
  | "port"
  | "interface"
  | "zone"
  | "hostname"
  | "gateway";

export const VARIABLE_TYPE_LABELS: Record<VariableType, string> = {
  string:    "Texto",
  network:   "Rede (CIDR)",
  ip:        "Endereço IP",
  port:      "Porta",
  interface: "Interface",
  zone:      "Zona / VLAN",
  hostname:  "Hostname",
  gateway:   "Gateway",
};

export interface TenantVariable {
  id: string;
  tenant_id: string;
  name: string;
  value: string;
  variable_type: VariableType;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeviceVariable {
  id: string;
  device_id: string;
  tenant_id: string;
  name: string;
  value: string;
  variable_type: VariableType;
  description: string | null;
  overrides_tenant: boolean;
  created_at: string;
  updated_at: string;
}

export interface ResolvedVariable {
  name: string;
  value: string;
  variable_type: VariableType;
  source: "device" | "tenant";
}

export interface DevicePreview {
  device_id: string;
  device_name: string;
  original_input: string;
  resolved_input: string;
  variables_resolved: ResolvedVariable[];
  unresolved_variables: string[];
  ready: boolean;
}

export interface BulkJobPreviewResponse {
  original_input: string;
  devices: DevicePreview[];
  all_ready: boolean;
}

export interface VariableFormData {
  name: string;
  value: string;
  variable_type: VariableType;
  description: string;
}
