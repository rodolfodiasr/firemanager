export type FirewallMigrationStatus =
  | "pending" | "analyzing" | "ready" | "applying" | "completed" | "failed";

export interface FirewallMigrationListItem {
  id: string;
  source_device_id: string | null;
  target_device_id: string | null;
  source_vendor: string;
  target_vendor: string;
  status: FirewallMigrationStatus;
  created_at: string;
  updated_at: string;
}

export interface FirewallMigration extends FirewallMigrationListItem {
  tenant_id: string;
  source_rules_raw: string | null;
  migration_plan: FirewallIR | null;
  commands_preview: string | null;
  warnings: string[] | null;
  error_message: string | null;
}

export interface FirewallIR {
  hostname: string | null;
  address_objects: AddressObject[];
  service_objects: ServiceObject[];
  policies: FirewallPolicy[];
  nat_rules: NatRule[];
  static_routes: StaticRoute[];
  warnings: string[];
}

export interface AddressObject {
  name: string;
  type: "host" | "network" | "fqdn" | "range" | "group";
  value: string;
  members: string[];
  comment: string;
}

export interface ServiceObject {
  name: string;
  type: "service" | "group";
  protocol: string;
  dst_ports: string[];
  members: string[];
  comment: string;
}

export interface FirewallPolicy {
  id: string;
  name: string;
  action: "accept" | "deny" | "drop";
  src_zones: string[];
  dst_zones: string[];
  src_addresses: string[];
  dst_addresses: string[];
  services: string[];
  nat: boolean;
  log: boolean;
  enabled: boolean;
  comment: string;
}

export interface NatRule {
  name: string;
  type: "snat" | "dnat" | "masquerade";
  src_addresses: string[];
  dst_addresses: string[];
  services: string[];
  translated_src: string | null;
  translated_dst: string | null;
  translated_port: string | null;
  enabled: boolean;
  comment: string;
}

export interface StaticRoute {
  network: string;
  gateway: string;
  interface: string | null;
  metric: number;
  enabled: boolean;
}

export interface FirewallMigrationCreate {
  source_device_id: string;
  target_device_id: string;
}
