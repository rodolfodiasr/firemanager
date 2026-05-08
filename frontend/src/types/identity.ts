export type ProviderType = "azure_ad" | "google_workspace" | "local_ad";
export type ActionStatus =
  | "pending_discovery"
  | "pending_approval"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";
export type TaskStatus = "pending" | "running" | "success" | "failed" | "skipped" | "not_found";
export type SystemType = "azure_ad" | "google_workspace" | "local_ad" | "ssh_linux" | "winrm_windows" | "database";

export interface IdentityProvider {
  id: string;
  name: string;
  provider_type: ProviderType;
  is_active: boolean;
  last_sync_at: string | null;
  last_sync_count: number | null;
  created_at: string;
}

export interface IdentityUser {
  id: string;
  provider_id: string;
  external_id: string;
  username: string;
  display_name: string | null;
  email: string | null;
  is_enabled: boolean;
  department: string | null;
  job_title: string | null;
  last_sign_in_raw: string | null;
  synced_at: string;
}

export interface LifecycleTask {
  id: string;
  system_type: SystemType;
  system_id: string | null;
  system_name: string;
  status: TaskStatus;
  result: string | null;
  error: string | null;
  executed_at: string | null;
}

export interface LifecycleAction {
  id: string;
  action_type: "offboard" | "onboard";
  target_username: string;
  display_name: string | null;
  email: string | null;
  status: ActionStatus;
  notes: string | null;
  created_at: string;
  approved_at: string | null;
  completed_at: string | null;
  tasks: LifecycleTask[];
}

export interface OrphanUser {
  provider_id: string;
  provider_name: string;
  provider_type: ProviderType;
  username: string;
  display_name: string | null;
  email: string | null;
  department: string | null;
  last_sign_in_raw: string | null;
}
