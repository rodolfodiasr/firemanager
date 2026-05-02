export type ServerOpStatus =
  | "pending_review"
  | "executing"
  | "completed"
  | "failed"
  | "rejected";

export interface ServerOperation {
  id: string;
  tenant_id: string;
  user_id: string;
  server_id: string;
  description: string;
  commands: string[];
  output: string | null;
  status: ServerOpStatus;
  error_message: string | null;
  review_comment: string | null;
  reviewer_id: string | null;
  reviewed_at: string | null;
  requester_name: string | null;
  requester_email: string | null;
  server_name: string | null;
  server_host: string | null;
  created_at: string;
  updated_at: string;
}
