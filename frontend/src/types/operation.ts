export type OperationStatus =
  | "pending"
  | "awaiting_approval"
  | "approved"
  | "executing"
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
  created_at: string;
  updated_at: string;
}

export interface ChatResponse {
  operation_id: string;
  status: OperationStatus;
  agent_message: string;
  ready_to_execute: boolean;
}
