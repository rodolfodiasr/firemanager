export type OperationStatus =
  | "pending"
  | "clarifying"
  | "awaiting_approval"
  | "approved"
  | "executing"
  | "pending_review"
  | "completed"
  | "failed"
  | "rejected";

export interface Operation {
  id: string;
  device_id: string;
  natural_language_input: string;
  intent: string | null;
  action_plan: Record<string, unknown> | null;
  status: OperationStatus;
  error_message: string | null;
  review_comment: string | null;
  reviewer_id: string | null;
  reviewed_at: string | null;
  executed_direct: boolean;
  bulk_job_id: string | null;
  parent_operation_id: string | null;
  created_at: string;
  updated_at: string;
  // Populated when fetched as part of BulkJobDetail
  device_name: string | null;
  device_category: string | null;
}

export interface ClarificationQuestion {
  id: string;
  question: string;
  field: string;
  options?: string[];
}

export type DiagnosticSeverity = "critical" | "high" | "medium" | "low" | "info";

export interface DiagnosticFinding {
  severity: DiagnosticSeverity;
  title: string;
  detail: string;
}

export interface DiagnosticAnalysis {
  summary: string;
  findings: DiagnosticFinding[];
  root_causes: string[];
  recommendations: string[];
  requires_immediate_action: boolean;
  suggested_follow_up_commands: string[];
}

export interface ChatResponse {
  operation_id: string;
  status: OperationStatus;
  agent_message: string;
  ready_to_execute: boolean;
  requires_approval: boolean;
  intent: string | null;
  preview_commands: string[];
  guardrail_blocked: boolean;
  device_id: string;
  // Clarification loop (Fase 40-A)
  clarifying: boolean;
  clarification_questions: ClarificationQuestion[];
  confidence_score: number | null;
}
