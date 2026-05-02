import apiClient from "./client";
import type { TenantRole } from "../types/tenant";

export type DeviceCategory = "firewall" | "switch" | "routing" | "server" | "hypervisor";
export type FunctionalModule = "compliance" | "remediation" | "server_analysis" | "bulk_jobs";

export interface CategoryRoleRead {
  user_id: string;
  tenant_id: string;
  category: DeviceCategory;
  role: TenantRole;
  granted_by: string | null;
  created_at: string;
}

export interface ModuleRoleRead {
  user_id: string;
  tenant_id: string;
  module: FunctionalModule;
  role: TenantRole;
  granted_by: string | null;
  created_at: string;
}

export interface UserPermissionProfile {
  user_id: string;
  user_name: string;
  user_email: string;
  tenant_role: TenantRole;
  category_roles: CategoryRoleRead[];
  module_roles: ModuleRoleRead[];
}

export const permissionsApi = {
  // ── Category roles ─────────────────────────────────────────────────────────
  listCategoryProfiles: () =>
    apiClient.get<UserPermissionProfile[]>("/category-roles/users").then((r) => r.data),

  getUserCategoryProfile: (userId: string) =>
    apiClient.get<UserPermissionProfile>(`/category-roles/users/${userId}`).then((r) => r.data),

  upsertCategoryRole: (userId: string, category: DeviceCategory, role: TenantRole) =>
    apiClient.put("/category-roles", { user_id: userId, category, role }).then((r) => r.data),

  deleteCategoryRole: (userId: string, category: DeviceCategory) =>
    apiClient.delete(`/category-roles/users/${userId}/categories/${category}`),

  replaceCategoryRoles: (userId: string, roles: { user_id: string; category: DeviceCategory; role: TenantRole }[]) =>
    apiClient.put<UserPermissionProfile>(`/category-roles/users/${userId}`, roles).then((r) => r.data),

  // ── Module roles ───────────────────────────────────────────────────────────
  listModuleProfiles: () =>
    apiClient.get<UserPermissionProfile[]>("/module-roles/users").then((r) => r.data),

  getUserModuleProfile: (userId: string) =>
    apiClient.get<UserPermissionProfile>(`/module-roles/users/${userId}`).then((r) => r.data),

  upsertModuleRole: (userId: string, module: FunctionalModule, role: TenantRole) =>
    apiClient.put("/module-roles", { user_id: userId, module, role }).then((r) => r.data),

  deleteModuleRole: (userId: string, module: FunctionalModule) =>
    apiClient.delete(`/module-roles/users/${userId}/modules/${module}`),

  replaceModuleRoles: (userId: string, roles: { user_id: string; module: FunctionalModule; role: TenantRole }[]) =>
    apiClient.put<UserPermissionProfile>(`/module-roles/users/${userId}`, roles).then((r) => r.data),
};
