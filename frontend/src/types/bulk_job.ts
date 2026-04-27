import type { Operation } from "./operation";

export type BulkJobStatus =
  | "pending"
  | "ready"
  | "executing"
  | "partial"
  | "completed"
  | "failed";

export interface BulkJob {
  id: string;
  tenant_id: string;
  created_by: string;
  description: string;
  status: BulkJobStatus;
  device_count: number;
  completed_count: number;
  failed_count: number;
  intent: string | null;
  error_summary: string | null;
  created_at: string;
  updated_at: string;
}

export interface CategoryPlanSummary {
  category: string;
  device_count: number;
  intent: string | null;
}

export interface BulkJobDetail extends BulkJob {
  operations: Operation[];
  category_plans: CategoryPlanSummary[] | null;
}

export interface BulkJobCreate {
  device_ids: string[];
  natural_language_input: string;
}
