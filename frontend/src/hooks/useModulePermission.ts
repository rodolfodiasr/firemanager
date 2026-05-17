import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "../store/authStore";
import { permissionsApi, type FunctionalModule } from "../api/permissions";
import type { TenantRole } from "../types/tenant";
import apiClient from "../api/client";

const ROLE_RANK: Record<TenantRole, number> = {
  admin:        5,
  analyst_n2:   4,
  analyst_sec:  4,
  analyst:      3,
  analyst_n1:   2,
  readonly:     1,
};

// Returns true if the current user's effective role for a module meets minRole.
// Effective role = max(tenant_role, module_role_override).
// Admins always pass.
export function useModulePermission(module: FunctionalModule, minRole: TenantRole): boolean {
  const tenantRole = useAuthStore((s) => s.tenantRole) as TenantRole | null;

  const { data: profile } = useQuery({
    queryKey: ["my-module-profile"],
    queryFn: async () => {
      const me = await apiClient.get("/auth/me").then((r) => r.data as { id: string });
      return permissionsApi.getUserModuleProfile(me.id).catch(() => null);
    },
    staleTime: 60_000,
  });

  if (!tenantRole) return false;
  if (tenantRole === "admin") return true;

  const baseRank = ROLE_RANK[tenantRole] ?? 0;

  // Check if there's a module-specific role override that elevates access
  const moduleRole = profile?.module_roles.find((mr) => mr.module === module);
  const effectiveRank = moduleRole
    ? Math.max(baseRank, ROLE_RANK[moduleRole.role] ?? 0)
    : baseRank;

  return effectiveRank >= (ROLE_RANK[minRole] ?? 0);
}

// Convenience: returns the effective TenantRole for a module
export function useEffectiveModuleRole(module: FunctionalModule): TenantRole | null {
  const tenantRole = useAuthStore((s) => s.tenantRole) as TenantRole | null;

  const { data: profile } = useQuery({
    queryKey: ["my-module-profile"],
    queryFn: async () => {
      const me = await apiClient.get("/auth/me").then((r) => r.data as { id: string });
      return permissionsApi.getUserModuleProfile(me.id).catch(() => null);
    },
    staleTime: 60_000,
  });

  if (!tenantRole) return null;
  if (tenantRole === "admin") return "admin";

  const baseRank = ROLE_RANK[tenantRole] ?? 0;
  const moduleRole = profile?.module_roles.find((mr) => mr.module === module);

  if (moduleRole) {
    const overrideRank = ROLE_RANK[moduleRole.role] ?? 0;
    if (overrideRank > baseRank) return moduleRole.role;
  }

  return tenantRole;
}
