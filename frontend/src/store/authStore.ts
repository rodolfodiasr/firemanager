import { create } from "zustand";
import type { User } from "../types/user";
import apiClient from "../api/client";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  login: (token: string, refreshToken: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem("access_token"),

  login: async (token, refreshToken) => {
    localStorage.setItem("access_token", token);
    localStorage.setItem("refresh_token", refreshToken);
    const me = await apiClient.get<User>("/auth/me").then((r) => r.data);
    set({ user: me, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ user: null, isAuthenticated: false });
  },

  fetchMe: async () => {
    try {
      const me = await apiClient.get<User>("/auth/me").then((r) => r.data);
      set({ user: me, isAuthenticated: true });
    } catch {
      set({ user: null, isAuthenticated: false });
    }
  },
}));
