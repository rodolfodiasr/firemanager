import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "../store/authStore";
import { permissionsApi } from "../api/permissions";
import apiClient from "../api/client";
import type { TenantRole } from "../types/tenant";

export type DashboardView = "operational" | "security" | "executive" | "infra";

export interface ViewDef {
  id: DashboardView;
  label: string;
}

const ROLE_RANK: Record<TenantRole, number> = {
  admin:       5,
  analyst_n2:  4,
  analyst_sec: 4,
  analyst:     3,
  analyst_n1:  2,
  readonly:    1,
};

export function useDashboardViews(): { views: ViewDef[]; defaultView: DashboardView } {
  const user       = useAuthStore((s) => s.user);
  const tenantRole = useAuthStore((s) => s.tenantRole) as TenantRole | null;
  const isSuperAdmin = user?.is_super_admin ?? false;
  const isAdmin      = isSuperAdmin || tenantRole === "admin";

  const { data: profile } = useQuery({
    queryKey: ["my-module-profile"],
    queryFn: async () => {
      const me = await apiClient.get("/auth/me").then((r) => r.data as { id: string });
      return permissionsApi.getUserModuleProfile(me.id).catch(() => null);
    },
    staleTime: 60_000,
    enabled: !!tenantRole && !isAdmin,
  });

  const baseRank = ROLE_RANK[tenantRole ?? "readonly"] ?? 0;

  const serverAnalysisModuleRole = profile?.module_roles.find(
    (mr) => mr.module === "server_analysis",
  );
  const serverAnalysisRank = isAdmin
    ? 5
    : serverAnalysisModuleRole
    ? Math.max(baseRank, ROLE_RANK[serverAnalysisModuleRole.role] ?? 0)
    : baseRank;

  // analyst_n2 sees executive; analyst_sec sees security; both ≠ same tab
  const canSeeExecutive = isAdmin || tenantRole === "analyst_n2";
  const canSeeSecurity  = isAdmin || tenantRole === "analyst_sec";
  const canSeeInfra     = isAdmin || serverAnalysisRank >= (ROLE_RANK["analyst_n2"] ?? 4);

  const views: ViewDef[] = [
    { id: "operational", label: "Operacional" },
    ...(canSeeSecurity  ? [{ id: "security"  as DashboardView, label: "Segurança"  }] : []),
    ...(canSeeExecutive ? [{ id: "executive" as DashboardView, label: "Executivo"  }] : []),
    ...(canSeeInfra     ? [{ id: "infra"     as DashboardView, label: "Infra N3"   }] : []),
  ];

  const defaultView: DashboardView =
    canSeeExecutive ? "executive" :
    canSeeSecurity  ? "security"  :
    canSeeInfra     ? "infra"     :
                      "operational";

  return { views, defaultView };
}
