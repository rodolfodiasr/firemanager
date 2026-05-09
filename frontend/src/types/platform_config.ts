export interface PlatformConfigKey {
  key: string;
  description: string | null;
  is_sensitive: boolean;
  is_set: boolean;
  updated_at: string;
  has_env_fallback: boolean;
}

export interface SetKeyPayload {
  value: string;
  description?: string;
}

export interface TestResult {
  ok: boolean;
  message: string;
}
