export type GlpiAnalysisStatus = "pending" | "pending_manual" | "analyzing" | "completed" | "failed" | "cancelled";

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
  // Analysis mode & enrichment sources
  auto_analysis_enabled: boolean;
  enrich_zabbix: boolean;
  enrich_wazuh: boolean;
  enrich_device_logs: boolean;
  device_logs_timeout_seconds: number;
  auto_correlate_devices: boolean;
  unmatched_to_manual_queue: boolean;
  force_analysis_on_security: boolean;
  force_analysis_on_recurrent: boolean;
  // KR loop
  auto_create_kr: boolean;
  kr_category_id: number | null;
  kr_bookstack_book_id: number | null;
  kr_bookstack_chapter_id: number | null;
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
  // Analysis mode & enrichment sources
  auto_analysis_enabled?: boolean;
  enrich_zabbix?: boolean;
  enrich_wazuh?: boolean;
  enrich_device_logs?: boolean;
  device_logs_timeout_seconds?: number;
  auto_correlate_devices?: boolean;
  unmatched_to_manual_queue?: boolean;
  force_analysis_on_security?: boolean;
  force_analysis_on_recurrent?: boolean;
  // KR loop
  auto_create_kr?: boolean;
  kr_category_id?: number | null;
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
  // Analysis mode & enrichment sources
  auto_analysis_enabled?: boolean;
  enrich_zabbix?: boolean;
  enrich_wazuh?: boolean;
  enrich_device_logs?: boolean;
  device_logs_timeout_seconds?: number;
  auto_correlate_devices?: boolean;
  unmatched_to_manual_queue?: boolean;
  force_analysis_on_security?: boolean;
  force_analysis_on_recurrent?: boolean;
  // KR loop
  auto_create_kr?: boolean;
  kr_category_id?: number | null;
}

export interface GlpiTestResult {
  success: boolean;
  message: string;
  latency_ms: number | null;
}

export type KbStatus = "documentado" | "parcialmente_documentado" | "sem_documentacao" | "nao_verificado";

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
  kb_status: KbStatus | null;
  kr_ticket_id: number | null;
  kr_draft_id: string | null;
  created_at: string;
  glpi_url: string | null;
}

export interface GlpiKrDraft {
  draft_id: string;
  title: string;
  status: "draft" | "approved" | "published" | "rejected";
  doc_type: string;
  created_at: string;
  glpi_analysis_id: string;
  glpi_ticket_id: number;
  glpi_ticket_title: string;
  kr_ticket_id: number | null;
  kb_status: KbStatus | null;
  bookstack_page_url: string | null;
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
  kb_docs: string[] | null;
  updated_at: string;
  glpi_url: string | null;
}
