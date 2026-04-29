export type DeviceCategory = "firewall" | "router" | "switch" | "l3_switch";

export type VendorEnum =
  // Firewalls
  | "fortinet"
  | "sonicwall"
  | "pfsense"
  | "opnsense"
  | "mikrotik"
  | "endian"
  // Routers / Switches
  | "cisco_ios"
  | "cisco_nxos"
  | "juniper"
  | "aruba"
  | "ubiquiti"
  | "dell"
  | "dell_n"
  | "hp_comware";

export type DeviceStatus = "online" | "offline" | "unknown" | "error";

export interface Device {
  id: string;
  name: string;
  vendor: VendorEnum;
  category: DeviceCategory;
  firmware_version: string | null;
  host: string;
  port: number;
  use_ssl: boolean;
  verify_ssl: boolean;
  status: DeviceStatus;
  last_seen: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeviceCredentials {
  auth_type: "token" | "user_pass" | "ssh";
  token?: string;
  username?: string;
  password?: string;
  ssh_port?: number;
  vdom?: string;
  os_version?: number;
  cmdline_password?: string;
}

export interface DeviceCreate {
  name: string;
  vendor: VendorEnum;
  category: DeviceCategory;
  firmware_version?: string;
  host: string;
  port: number;
  credentials: DeviceCredentials;
  use_ssl: boolean;
  verify_ssl: boolean;
  notes?: string;
}
