import type { Attachment, ChatResponse, Operation } from "../types/operation";
import apiClient from "./client";

export const operationsApi = {
  startChat: (
    deviceId: string,
    message: string,
    parentOperationId?: string,
    useBookstackContext: boolean = true,
    attachment?: Attachment,
  ) =>
    apiClient
      .post<ChatResponse>("/operations", {
        device_id: deviceId,
        natural_language_input: message,
        parent_operation_id: parentOperationId ?? null,
        use_bookstack_context: useBookstackContext,
        attachment: attachment ?? null,
      })
      .then((r) => r.data),

  continueChat: (operationId: string, content: string, attachment?: Attachment) =>
    apiClient
      .post<ChatResponse>(`/operations/${operationId}/chat`, { role: "user", content, attachment: attachment ?? null })
      .then((r) => r.data),

  transcribe: (audio: Blob): Promise<{ text: string }> => {
    const form = new FormData();
    form.append("audio", audio, "recording.webm");
    return apiClient.post<{ text: string }>("/operations/transcribe", form, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data);
  },

  parseFile: (file: File): Promise<{ text: string }> => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<{ text: string }>("/operations/parse-file", form, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data);
  },

  execute: (operationId: string) =>
    apiClient.post<Operation>(`/operations/${operationId}/execute`).then((r) => r.data),

  submitForReview: (operationId: string) =>
    apiClient.post<Operation>(`/operations/${operationId}/submit-review`).then((r) => r.data),

  list: () => apiClient.get<Operation[]>("/operations").then((r) => r.data),

  get: (id: string) => apiClient.get<Operation>(`/operations/${id}`).then((r) => r.data),

  getTutorial: (id: string) =>
    apiClient.get<{ tutorial: string }>(`/operations/${id}/tutorial`).then((r) => r.data),

  clarify: (operationId: string, answers: { id: string; answer: string }[]) =>
    apiClient
      .post<ChatResponse>(`/operations/${operationId}/clarify`, { answers })
      .then((r) => r.data),

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
