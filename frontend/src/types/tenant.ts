export type TenantRole = "admin" | "analyst_n2" | "analyst_n1" | "readonly" | "analyst";

export interface TenantInfo {
  id: string;
  name: string;
  slug: string;
}

export interface TenantRead extends TenantInfo {
  is_active: boolean;
  created_at: string;
}

export interface TenantMember {
  user_id: string;
  tenant_id: string;
  role: TenantRole;
  email: string;
  name: string;
  is_active: boolean;
}
