import { create } from "zustand";
import type { TenantInfo } from "../types/tenant";
import type { User } from "../types/user";
import apiClient from "../api/client";

interface AuthState {
  user:            User | null;
  tenant:          TenantInfo | null;
  tenantRole:      string | null;
  pendingTenants:  TenantInfo[] | null;  // set when login returns multiple tenants
  preToken:        string | null;
  isAuthenticated: boolean;

  login:           (token: string, refreshToken: string) => Promise<void>;
  setPendingTenants: (preToken: string, tenants: TenantInfo[]) => void;
  selectTenant:    (tenantId: string) => Promise<void>;
  logout:          () => void;
  fetchMe:         () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user:            null,
  tenant:          null,
  tenantRole:      null,
  pendingTenants:  null,
  preToken:        null,
  isAuthenticated: !!localStorage.getItem("access_token"),

  login: async (token, refreshToken) => {
    localStorage.setItem("access_token", token);
    localStorage.setItem("refresh_token", refreshToken);
    const me = await apiClient.get<User>("/auth/me").then((r) => r.data);
    const myTenants = await apiClient
      .get<TenantInfo[]>("/auth/me/tenants")
      .then((r) => r.data)
      .catch(() => []);

    // Decode tenant_id from JWT payload (middle segment)
    let tenantId: string | null = null;
    let role: string | null = null;
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      tenantId = payload.tenant_id ?? null;
      role     = payload.role     ?? null;
    } catch { /* ignore */ }

    const activeTenant = myTenants.find((t) => t.id === tenantId) ?? myTenants[0] ?? null;

    set({
      user: me,
      tenant: activeTenant,
      tenantRole: role,
      pendingTenants: null,
      preToken: null,
      isAuthenticated: true,
    });
  },

  setPendingTenants: (preToken, tenants) => {
    set({ preToken, pendingTenants: tenants, isAuthenticated: false });
  },

  selectTenant: async (tenantId: string) => {
    const { preToken } = get();
    const resp = await apiClient.post<{ access_token: string; refresh_token: string }>(
      "/auth/select-tenant",
      { pre_token: preToken, tenant_id: tenantId }
    );
    await get().login(resp.data.access_token, resp.data.refresh_token);
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ user: null, tenant: null, tenantRole: null, pendingTenants: null, preToken: null, isAuthenticated: false });
  },

  fetchMe: async () => {
    try {
      const me = await apiClient.get<User>("/auth/me").then((r) => r.data);
      const myTenants = await apiClient
        .get<TenantInfo[]>("/auth/me/tenants")
        .then((r) => r.data)
        .catch(() => []);

      const token = localStorage.getItem("access_token") ?? "";
      let tenantId: string | null = null;
      let role: string | null = null;
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        tenantId = payload.tenant_id ?? null;
        role     = payload.role     ?? null;
      } catch { /* ignore */ }

      const activeTenant = myTenants.find((t) => t.id === tenantId) ?? myTenants[0] ?? null;
      set({ user: me, tenant: activeTenant, tenantRole: role, isAuthenticated: true });
    } catch {
      set({ user: null, tenant: null, tenantRole: null, isAuthenticated: false });
    }
  },
}));
