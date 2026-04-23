import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../api/client";
import { useAuthStore } from "../store/authStore";
import type { TokenResponse } from "../types/user";

export function useAuth() {
  const { user, isAuthenticated, login, logout, fetchMe } = useAuthStore();
  const navigate = useNavigate();

  const signIn = useCallback(
    async (email: string, password: string, totpCode?: string) => {
      const resp = await apiClient.post<TokenResponse>("/auth/login", {
        email,
        password,
        totp_code: totpCode,
      });
      await login(resp.data.access_token, resp.data.refresh_token);
      navigate("/");
    },
    [login, navigate]
  );

  const signOut = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  return { user, isAuthenticated, signIn, signOut, fetchMe };
}
