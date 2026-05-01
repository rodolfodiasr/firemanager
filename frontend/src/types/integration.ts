export type IntegrationType = "shodan" | "wazuh" | "openvas" | "nmap" | "zabbix" | "bookstack";

export interface Integration {
  id: string;
  tenant_id: string | null;
  type: IntegrationType;
  name: string;
  is_active: boolean;
  scope: "global" | "tenant";
  created_at: string;
  updated_at: string;
}

export interface TestResult {
  success: boolean;
  message: string;
  latency_ms?: number;
}

export interface IntegrationCreate {
  type: IntegrationType;
  name: string;
  config: Record<string, unknown>;
  is_active?: boolean;
  tenant_id?: string | null;
}

export interface IntegrationUpdate {
  name?: string;
  config?: Record<string, unknown>;
  is_active?: boolean;
}
