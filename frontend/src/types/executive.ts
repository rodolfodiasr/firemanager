export interface SecurityPosture {
  generated_at: string;
  risk_score: number;
  identity: {
    total_users: number;
    orphan_accounts: number;
    orphan_percentage: number;
  };
  lifecycle_30d: {
    offboards_completed: number;
    onboards_completed: number;
    pending_actions: number;
  };
  infrastructure: {
    servers: number;
    databases: number;
  };
  alerts_7d: {
    total: number;
    critical: number;
  };
  recent_actions: {
    id: string;
    action_type: string;
    target_username: string;
    status: string;
    created_at: string;
  }[];
}
