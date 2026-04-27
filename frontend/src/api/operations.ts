import type { ChatResponse, Operation } from "../types/operation";
import apiClient from "./client";

export const operationsApi = {
  startChat: (deviceId: string, message: string, parentOperationId?: string) =>
    apiClient
      .post<ChatResponse>("/operations", {
        device_id: deviceId,
        natural_language_input: message,
        parent_operation_id: parentOperationId ?? null,
      })
      .then((r) => r.data),

  continueChat: (operationId: string, content: string) =>
    apiClient
      .post<ChatResponse>(`/operations/${operationId}/chat`, { role: "user", content })
      .then((r) => r.data),

  execute: (operationId: string) =>
    apiClient.post<Operation>(`/operations/${operationId}/execute`).then((r) => r.data),

  submitForReview: (operationId: string) =>
    apiClient.post<Operation>(`/operations/${operationId}/submit-review`).then((r) => r.data),

  list: () => apiClient.get<Operation[]>("/operations").then((r) => r.data),

  get: (id: string) => apiClient.get<Operation>(`/operations/${id}`).then((r) => r.data),

  getTutorial: (id: string) =>
    apiClient.get<{ tutorial: string }>(`/operations/${id}/tutorial`).then((r) => r.data),

  createDirectSSH: (body: {
    device_id: string;
    description: string;
    ssh_commands: string[];
    parent_operation_id?: string;
    template_slug?: string;
    template_params?: Record<string, string>;
  }) =>
    apiClient.post<{ id: string; status: string }>("/operations/direct-ssh", body).then((r) => r.data),
};
