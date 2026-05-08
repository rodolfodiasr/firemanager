import apiClient from "./client";
import type { ExternalConnector, OnboardingProfile, OnboardingActionCreate } from "../types/onboarding";

export const onboardingApi = {
  listConnectors: () =>
    apiClient.get<ExternalConnector[]>("/onboarding/connectors").then((r) => r.data),

  createConnector: (data: { name: string; connector_type: string; config: Record<string, unknown> }) =>
    apiClient.post<ExternalConnector>("/onboarding/connectors", data).then((r) => r.data),

  deleteConnector: (id: string) =>
    apiClient.delete(`/onboarding/connectors/${id}`),

  testConnector: (id: string) =>
    apiClient.post<{ success: boolean; message: string }>(`/onboarding/connectors/${id}/test`).then((r) => r.data),

  listProfiles: () =>
    apiClient.get<OnboardingProfile[]>("/onboarding/profiles").then((r) => r.data),

  createProfile: (data: Omit<OnboardingProfile, "id" | "created_at">) =>
    apiClient.post<OnboardingProfile>("/onboarding/profiles", data).then((r) => r.data),

  updateProfile: (id: string, data: Omit<OnboardingProfile, "id" | "created_at">) =>
    apiClient.put<OnboardingProfile>(`/onboarding/profiles/${id}`, data).then((r) => r.data),

  deleteProfile: (id: string) =>
    apiClient.delete(`/onboarding/profiles/${id}`),

  triggerOnboarding: (data: OnboardingActionCreate) =>
    apiClient.post<{ action_id: string; status: string }>("/onboarding/actions", data).then((r) => r.data),
};
