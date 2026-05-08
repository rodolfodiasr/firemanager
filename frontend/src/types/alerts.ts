export type AlertChannelType = "slack" | "teams" | "email" | "webhook" | "jira";
export type AlertSeverity = "info" | "warning" | "critical";
export type AlertTrigger =
  | "offboard_completed"
  | "onboard_completed"
  | "task_failed"
  | "health_check_failed"
  | "orphan_detected";

export interface AlertChannel {
  id: string;
  name: string;
  channel_type: AlertChannelType;
  is_active: boolean;
  created_at: string;
}

export interface AlertRule {
  id: string;
  name: string;
  trigger: AlertTrigger;
  severity: AlertSeverity;
  channel_ids: string[];
  is_active: boolean;
  created_at: string;
}

export interface AlertEvent {
  id: string;
  trigger: string;
  severity: AlertSeverity;
  title: string;
  body: string;
  channels_result: Record<string, string>;
  created_at: string;
}
