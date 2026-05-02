import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../api/client";
import { useAuthStore } from "../store/authStore";
import type { TokenResponse } from "../types/user";

export function useAuth() {
  const store = useAuthStore();
  const navigate = useNavigate();

  const signIn = useCallback(
    async (email: string, password: string, totpCode?: string) => {
      const resp = await apiClient.post<TokenResponse>("/auth/login", {
        email,
        password,
        totp_code: totpCode,
      });

      const data = resp.data;

      // Multiple tenants — need user to pick one
      if (data.pre_token && data.tenants) {
        store.setPendingTenants(data.pre_token, data.tenants);
        return; // Login page renders tenant picker
      }

      // Single tenant or super admin — token ready
      if (data.access_token && data.refresh_token) {
        await store.login(data.access_token, data.refresh_token);
        navigate("/");
      }
    },
    [store, navigate]
  );

  const selectTenant = useCallback(
    async (tenantId: string) => {
      await store.selectTenant(tenantId);
      navigate("/");
    },
    [store, navigate]
  );

  const assumeTenant = useCallback(
    async (tenantId: string) => {
      await store.assumeTenant(tenantId);
      navigate("/");
    },
    [store, navigate]
  );

  const exitAssumedTenant = useCallback(() => {
    store.exitAssumedTenant();
    navigate("/");
  }, [store, navigate]);

  const signOut = useCallback(() => {
    store.logout();
    navigate("/login");
  }, [store, navigate]);

  return {
    user:           store.user,
    tenant:         store.tenant,
    tenantRole:     store.tenantRole,
    pendingTenants: store.pendingTenants,
    isAuthenticated: store.isAuthenticated,
    signIn,
    selectTenant,
    assumeTenant,
    exitAssumedTenant,
    signOut,
    fetchMe: store.fetchMe,
  };
}
