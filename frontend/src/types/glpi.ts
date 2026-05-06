export type GlpiAnalysisStatus = "pending" | "analyzing" | "completed" | "failed";

export interface GlpiIntegration {
  id: string;
  tenant_id: string;
  glpi_url: string;
  app_token: string;
  username: string;
  verify_ssl: boolean;
  is_active: boolean;
  min_priority: number;
  trigger_types: number[];
  trigger_categories: number[];
  tag_analyzed: string;
  poll_interval_minutes: number;
  lookback_hours: number;
  created_at: string;
  updated_at: string;
}

export interface GlpiIntegrationCreate {
  glpi_url: string;
  app_token: string;
  username: string;
  password: string;
  verify_ssl?: boolean;
  min_priority?: number;
  trigger_types?: number[];
  trigger_categories?: number[];
  tag_analyzed?: string;
  poll_interval_minutes?: number;
  lookback_hours?: number;
}

export interface GlpiIntegrationUpdate {
  glpi_url?: string;
  app_token?: string;
  username?: string;
  password?: string;
  verify_ssl?: boolean;
  is_active?: boolean;
  min_priority?: number;
  trigger_types?: number[];
  poll_interval_minutes?: number;
  lookback_hours?: number;
}

export interface GlpiTestResult {
  success: boolean;
  message: string;
  latency_ms: number | null;
}

export interface GlpiAnalysisListItem {
  id: string;
  glpi_ticket_id: number;
  glpi_itemtype: string;
  glpi_ticket_title: string;
  status: GlpiAnalysisStatus;
  confianca: number | null;
  is_security_incident: boolean | null;
  is_recurrent: boolean | null;
  recurrence_count: number | null;
  created_at: string;
  glpi_url: string | null;
}

export interface GlpiTicketAnalysis extends GlpiAnalysisListItem {
  tenant_id: string;
  glpi_integration_id: string;
  glpi_ticket_content: string | null;
  diagnostico: string | null;
  acoes_imediatas: string | null;
  plano_remediacao: string | null;
  causa_raiz: string | null;
  prevencao: string | null;
  related_ticket_ids: number[] | null;
  glpi_followup_id: number | null;
  error_message: string | null;
  updated_at: string;
  glpi_url: string | null;
}
