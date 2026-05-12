import apiClient from "./client";
import type { AssistantMessage, AssistantSession } from "../store/assistantStore";

interface AssistantMessageResponse {
  id: string;
  session_id: string;
  role: string;
  content: string;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  rag_context_used: boolean;
  created_at: string;
}

interface AssistantSessionResponse {
  id: string;
  title: string | null;
  model_used: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

interface CapabilitiesResponse {
  openai_available: boolean;
  default_model: string;
}

function mapMessage(r: AssistantMessageResponse): AssistantMessage {
  return {
    id: r.id,
    sessionId: r.session_id,
    role: r.role as "user" | "assistant",
    content: r.content,
    model: r.model,
    inputTokens: r.input_tokens,
    outputTokens: r.output_tokens,
    ragContextUsed: r.rag_context_used,
    createdAt: r.created_at,
  };
}

function mapSession(r: AssistantSessionResponse): AssistantSession {
  return {
    id: r.id,
    title: r.title,
    modelUsed: r.model_used,
    messageCount: r.message_count,
    createdAt: r.created_at,
    updatedAt: r.updated_at,
  };
}

export const assistantApi = {
  capabilities: () =>
    apiClient.get<CapabilitiesResponse>("/assistant/capabilities").then((r) => r.data),

  chat: (data: { content: string; session_id?: string | null; model?: string | null }) =>
    apiClient
      .post<AssistantMessageResponse>("/assistant/chat", {
        content: data.content,
        session_id: data.session_id ?? null,
        model: data.model ?? null,
      })
      .then((r) => mapMessage(r.data)),

  listSessions: () =>
    apiClient
      .get<AssistantSessionResponse[]>("/assistant/sessions")
      .then((r) => r.data.map(mapSession)),

  getSession: (id: string) =>
    apiClient
      .get<{ session: AssistantSessionResponse; messages: AssistantMessageResponse[] }>(
        `/assistant/sessions/${id}`
      )
      .then((r) => ({
        session: mapSession(r.data.session),
        messages: r.data.messages.map(mapMessage),
      })),

  deleteSession: (id: string) =>
    apiClient.delete(`/assistant/sessions/${id}`).then((r) => r.data),
};
