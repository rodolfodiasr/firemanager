export type HypervisorType = "vmware_vcenter" | "proxmox" | "hyper_v";

export interface VmHypervisor {
  id: string;
  tenant_id: string;
  name: string;
  hypervisor_type: HypervisorType;
  host: string;
  verify_ssl: boolean;
  is_active: boolean;
  last_sync_at: string | null;
  last_vm_count: number | null;
  created_at: string;
}

export interface VmInventoryItem {
  id: string;
  hypervisor_id: string;
  vm_id: string;
  vm_name: string;
  power_state: string;
  os_type: string | null;
  cpu_count: number | null;
  ram_mb: number | null;
  disk_gb: number | null;
  ip_addresses: string[];
  tags: string[] | null;
  synced_at: string;
}

export interface MigrationRunbook {
  id: string;
  tenant_id: string;
  title: string;
  vm_ids: string[];
  ai_runbook: string | null;
  source_hypervisor_id: string | null;
  target_hypervisor_id: string | null;
  status: "draft" | "generating" | "ready" | "exported";
  bookstack_page_url: string | null;
  created_at: string;
  updated_at: string;
}
