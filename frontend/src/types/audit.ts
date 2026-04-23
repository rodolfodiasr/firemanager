export interface AuditLog {
  id: string;
  user_id: string | null;
  device_id: string | null;
  operation_id: string | null;
  action: string;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  record_hash: string;
  created_at: string;
}
