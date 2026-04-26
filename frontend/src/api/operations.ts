import type { ChatResponse, Operation } from "../types/operation";
import apiClient from "./client";

export const operationsApi = {
  startChat: (deviceId: string, message: string) =>
    apiClient
      .post<ChatResponse>("/operations", {
        device_id: deviceId,
        natural_language_input: message,
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
};
