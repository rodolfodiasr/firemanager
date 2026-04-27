import type { TenantInfo } from "./tenant";

export type UserRole = "admin" | "operator" | "viewer";

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
  mfa_enabled: boolean;
  is_super_admin: boolean;
}

export interface TokenResponse {
  access_token?: string;
  refresh_token?: string;
  pre_token?: string;
  tenants?: TenantInfo[];
  token_type: string;
}
