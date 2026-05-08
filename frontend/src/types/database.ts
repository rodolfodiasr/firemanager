export type DbType = "postgresql" | "mysql" | "mariadb" | "sqlserver" | "oracle";
export type AuditStatus = "running" | "completed" | "failed";

export interface DatabaseConnector {
  id: string;
  tenant_id: string;
  server_id: string | null;
  name: string;
  description: string | null;
  db_type: DbType;
  host: string;
  port: number;
  database_name: string;
  is_active: boolean;
  last_tested_at: string | null;
  last_test_ok: boolean | null;
  last_test_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface DbFinding {
  type: string;
  severity: "high" | "medium" | "low";
  user: string;
  detail: string;
}

export interface DbUser {
  name: string;
  is_superuser: boolean;
  can_login: boolean;
  is_system: boolean;
  password_never_expires: boolean;
  last_login: string | null;
  days_since_login: number | null;
  [key: string]: unknown;
}

export interface AuditReport {
  id: string;
  connector_id: string;
  status: AuditStatus;
  db_version: string | null;
  user_count: number;
  finding_count: number;
  users: DbUser[];
  findings: DbFinding[];
  ai_summary: string;
  ai_recommendations: string[];
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface AuditSummary {
  id: string;
  connector_id: string;
  status: AuditStatus;
  user_count: number;
  finding_count: number;
  db_version: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface TestResult {
  success: boolean;
  message: string;
}
