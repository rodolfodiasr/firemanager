import apiClient from "./client";

export interface FirmwareVersionRead {
  id: string;
  device_id: string;
  version: string;
  vendor_label: string;
  model: string | null;
  build: string | null;
  read_at: string;
  read_method: string;
}

export interface FirmwareCVERead {
  id: string;
  cve_id: string;
  vendor: string;
  product: string;
  affected_versions: Record<string, unknown>;
  cvss_v3: number | null;
  cvss_v2: number | null;
  severity: string;
  description: string;
  published_at: string | null;
  nvd_url: string;
  synced_at: string;
}

export interface FirmwareVulnRead {
  id: string;
  device_id: string;
  cve_id: string;
  device_version: string;
  detected_at: string;
  status: string;
  accepted_by: string | null;
  accepted_reason: string | null;
  patched_at: string | null;
  cve: FirmwareCVERead | null;
}

export interface DeviceFirmwareSummary {
  device_id: string;
  current_version: string | null;
  last_read_at: string | null;
  open_cves: number;
  critical_cves: number;
  high_cves: number;
  worst_severity: string;
}

export interface FirmwareRiskSummary {
  devices_with_vulns: number;
  total_open_cves: number;
  critical_cves: number;
  high_cves: number;
  top_affected: DeviceFirmwareSummary[];
}

export const firmwareApi = {
  getSummary: (deviceId: string) =>
    apiClient.get<DeviceFirmwareSummary>(`/devices/${deviceId}/firmware/summary`).then(r => r.data),

  getVersions: (deviceId: string) =>
    apiClient.get<FirmwareVersionRead[]>(`/devices/${deviceId}/firmware/versions`).then(r => r.data),

  getVulnerabilities: (deviceId: string, status = "open") =>
    apiClient.get<FirmwareVulnRead[]>(`/devices/${deviceId}/firmware/vulnerabilities`, { params: { status } }).then(r => r.data),

  triggerRefresh: (deviceId: string) =>
    apiClient.post<{ task_id: string; status: string }>(`/devices/${deviceId}/firmware/refresh`).then(r => r.data),

  acceptRisk: (vulnId: string, reason: string) =>
    apiClient.patch(`/firmware/vulnerabilities/${vulnId}/accept`, { reason }).then(r => r.data),

  getRiskSummary: () =>
    apiClient.get<FirmwareRiskSummary>("/firmware/risk-summary").then(r => r.data),

  listCVEs: (vendor?: string, severity?: string) =>
    apiClient.get<FirmwareCVERead[]>("/firmware/cves", { params: { vendor, severity } }).then(r => r.data),
};
