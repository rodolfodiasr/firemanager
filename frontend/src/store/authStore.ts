import { create } from "zustand";
import type { TenantInfo } from "../types/tenant";
import type { User } from "../types/user";
import apiClient from "../api/client";

interface AuthState {
  user:             User | null;
  tenant:           TenantInfo | null;
  tenantRole:       string | null;
  pendingTenants:   TenantInfo[] | null;
  preToken:         string | null;
  isAuthenticated:  boolean;

  // Support mode — super admin viewing a tenant as read-only
  supportMode:      boolean;
  supportTenantName: string | null;
  _savedToken:      string | null;

  login:              (token: string, refreshToken: string) => Promise<void>;
  setPendingTenants:  (preToken: string, tenants: TenantInfo[]) => void;
  selectTenant:       (tenantId: string) => Promise<void>;
  assumeTenant:       (tenantId: string) => Promise<void>;
  exitAssumedTenant:  () => void;
  logout:             () => void;
  fetchMe:            () => Promise<void>;
  enterSupportMode:   (supportToken: string, tenantName: string) => void;
  exitSupportMode:    () => void;
}

function decodeJwtPayload(token: string): Record<string, unknown> {
  try {
    return JSON.parse(atob(token.split(".")[1]));
  } catch {
    return {};
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user:             null,
  tenant:           null,
  tenantRole:       null,
  pendingTenants:   null,
  preToken:         null,
  isAuthenticated:  !!localStorage.getItem("access_token"),
  supportMode:      false,
  supportTenantName: null,
  _savedToken:      null,

  login: async (token, refreshToken) => {
    localStorage.setItem("access_token", token);
    localStorage.setItem("refresh_token", refreshToken);
    const me = await apiClient.get<User>("/auth/me").then((r) => r.data);
    const myTenants = await apiClient
      .get<TenantInfo[]>("/auth/me/tenants")
      .then((r) => r.data)
      .catch(() => []);

    const payload = decodeJwtPayload(token);
    const tenantId = (payload.tenant_id as string) ?? null;
    const role     = (payload.role as string)      ?? null;

    const activeTenant = myTenants.find((t) => t.id === tenantId) ?? myTenants[0] ?? null;

    set({
      user: me,
      tenant: activeTenant,
      tenantRole: role,
      pendingTenants: null,
      preToken: null,
      isAuthenticated: true,
      supportMode: false,
      supportTenantName: null,
      _savedToken: null,
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

  assumeTenant: async (tenantId: string) => {
    const savedToken = localStorage.getItem("access_token") ?? "";
    const resp = await apiClient.post<{ access_token: string; refresh_token: string }>(
      "/auth/assume-tenant",
      { tenant_id: tenantId }
    );
    localStorage.setItem("access_token", resp.data.access_token);
    localStorage.setItem("refresh_token", resp.data.refresh_token);
    const me = await apiClient.get<User>("/auth/me").then((r) => r.data);
    const myTenants = await apiClient.get<TenantInfo[]>("/auth/me/tenants").then((r) => r.data).catch(() => []);
    const payload = JSON.parse(atob(resp.data.access_token.split(".")[1]));
    const tid = payload.tenant_id as string;
    const activeTenant = myTenants.find((t) => t.id === tid) ?? null;
    set({ user: me, tenant: activeTenant, tenantRole: "admin", isAuthenticated: true, _savedToken: savedToken });
  },

  exitAssumedTenant: () => {
    const { _savedToken } = get();
    if (_savedToken) {
      localStorage.setItem("access_token", _savedToken);
      localStorage.removeItem("refresh_token");
    }
    set({ tenant: null, tenantRole: "super_admin", _savedToken: null });
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({
      user: null,
      tenant: null,
      tenantRole: null,
      pendingTenants: null,
      preToken: null,
      isAuthenticated: false,
      supportMode: false,
      supportTenantName: null,
      _savedToken: null,
    });
  },

  fetchMe: async () => {
    try {
      const me = await apiClient.get<User>("/auth/me").then((r) => r.data);
      const myTenants = await apiClient
        .get<TenantInfo[]>("/auth/me/tenants")
        .then((r) => r.data)
        .catch(() => []);

      const token = localStorage.getItem("access_token") ?? "";
      const payload = decodeJwtPayload(token);
      const tenantId = (payload.tenant_id as string) ?? null;
      const role     = (payload.role as string)      ?? null;

      const activeTenant = myTenants.find((t) => t.id === tenantId) ?? myTenants[0] ?? null;
      set({ user: me, tenant: activeTenant, tenantRole: role, isAuthenticated: true });
    } catch {
      set({ user: null, tenant: null, tenantRole: null, isAuthenticated: false });
    }
  },

  enterSupportMode: (supportToken: string, tenantName: string) => {
    const savedToken = localStorage.getItem("access_token") ?? "";
    localStorage.setItem("access_token", supportToken);
    set({ supportMode: true, supportTenantName: tenantName, _savedToken: savedToken });
  },

  exitSupportMode: () => {
    const { _savedToken } = get();
    if (_savedToken) {
      localStorage.setItem("access_token", _savedToken);
    }
    set({ supportMode: false, supportTenantName: null, _savedToken: null });
  },
}));
