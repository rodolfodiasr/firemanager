export interface DeviceInGroup {
  id: string;
  name: string;
  vendor: string;
  category: string;
  status: string;
  host: string;
}

export interface DeviceGroup {
  id: string;
  tenant_id: string;
  created_by: string;
  name: string;
  description: string | null;
  device_count: number;
  category_counts: Record<string, number>;
  created_at: string;
  updated_at: string;
}

export interface DeviceGroupDetail extends DeviceGroup {
  devices: DeviceInGroup[];
}

export interface DeviceGroupCreate {
  name: string;
  description?: string | null;
  device_ids: string[];
}

export interface DeviceGroupUpdate {
  name?: string | null;
  description?: string | null;
  device_ids?: string[] | null;
}
