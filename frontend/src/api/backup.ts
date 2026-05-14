import axios from "axios";

const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export interface BackupConfig {
  id: string;
  name: string;
  backup_type: "platform" | "tenant";
  destination: "local" | "s3" | "sftp";
  schedule_cron: string | null;
  retention_count: number;
  local_path: string | null;
  s3_bucket: string | null;
  s3_prefix: string | null;
  sftp_host: string | null;
  sftp_path: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BackupJob {
  id: string;
  config_id: string;
  tenant_id: string | null;
  status: "pending" | "running" | "success" | "failed";
  backup_type: "platform" | "tenant";
  destination: "local" | "s3" | "sftp";
  file_path: string | null;
  file_size_bytes: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface BackupConfigCreate {
  name: string;
  destination: "local" | "s3" | "sftp";
  schedule_cron?: string | null;
  retention_count?: number;
  local_path?: string | null;
  s3_bucket?: string | null;
  s3_prefix?: string | null;
  s3_region?: string | null;
  s3_access_key?: string | null;
  s3_secret_key?: string | null;
  sftp_host?: string | null;
  sftp_port?: number | null;
  sftp_user?: string | null;
  sftp_password?: string | null;
  sftp_private_key?: string | null;
  sftp_path?: string | null;
}

// ── Platform backup (super admin) ─────────────────────────────────────────────

export const adminBackupApi = {
  listConfigs: () =>
    api.get<BackupConfig[]>("/admin/backup/configs").then((r) => r.data),

  createConfig: (data: BackupConfigCreate) =>
    api.post<BackupConfig>("/admin/backup/configs", data).then((r) => r.data),

  deleteConfig: (id: string) =>
    api.delete(`/admin/backup/configs/${id}`).then((r) => r.data),

  triggerBackup: (configId: string) =>
    api.post<{ job_id: string; status: string }>(`/admin/backup/configs/${configId}/run`).then((r) => r.data),

  listJobs: () =>
    api.get<BackupJob[]>("/admin/backup/jobs").then((r) => r.data),

  triggerRestore: (jobId: string) =>
    api.post<{ status: string; job_id: string }>(`/admin/backup/jobs/${jobId}/restore`).then((r) => r.data),
};

// ── Tenant backup (tenant admin) ─────────────────────────────────────────────

export const tenantBackupApi = {
  listConfigs: () =>
    api.get<BackupConfig[]>("/backup/configs").then((r) => r.data),

  createConfig: (data: BackupConfigCreate) =>
    api.post<BackupConfig>("/backup/configs", data).then((r) => r.data),

  deleteConfig: (id: string) =>
    api.delete(`/backup/configs/${id}`).then((r) => r.data),

  triggerBackup: (configId: string) =>
    api.post<{ job_id: string; status: string }>(`/backup/configs/${configId}/run`).then((r) => r.data),

  listJobs: () =>
    api.get<BackupJob[]>("/backup/jobs").then((r) => r.data),

  triggerRestore: (jobId: string) =>
    api.post<{ status: string; job_id: string }>(`/backup/jobs/${jobId}/restore`).then((r) => r.data),
};
