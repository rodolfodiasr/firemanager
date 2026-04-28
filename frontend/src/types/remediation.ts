export type RemediationStatus =
  | "pending_approval"
  | "approved"
  | "executing"
  | "completed"
  | "partial"
  | "rejected";

export type RemediationRisk = "low" | "medium" | "high";

export type CommandStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "executing"
  | "completed"
  | "failed"
  | "skipped";

export interface RemediationCommand {
  id: string;
  plan_id: string;
  order: number;
  description: string;
  command: string;
  risk: RemediationRisk;
  status: CommandStatus;
  output: string | null;
  executed_at: string | null;
}

export interface RemediationPlan {
  id: string;
  tenant_id: string;
  server_id: string;
  session_id: string | null;
  request: string;
  summary: string;
  status: RemediationStatus;
  reviewer_comment: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
  commands: RemediationCommand[];
}

export interface RemediationRequest {
  server_id: string;
  request: string;
  session_id?: string;
}
