export interface TenantBranding {
  id: string;
  tenant_id: string;
  company_name: string | null;
  primary_color: string | null; // hex
  logo_url: string | null;
  favicon_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiKey {
  id: string;
  tenant_id: string;
  name: string;
  key_prefix: string; // first 8 chars
  permissions: string[];
  is_active: boolean;
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
}

export interface ApiKeyCreate {
  name: string;
  permissions: string[];
  expires_at?: string | null;
}

export interface ApiKeyCreated extends ApiKey {
  raw_key: string; // returned only once on creation
}
