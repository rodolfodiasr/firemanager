import apiClient from "./client";
import type {
  AssistantMessage,
  AssistantSession,
  AssistantFolder,
} from "../store/assistantStore";

// ── Doc Draft types ───────────────────────────────────────────────────────────

export interface DocDraft {
  id: string;
  session_id: string;
  tenant_id: string;
  created_by: string | null;
  title: string;
  content: string;
  status: "draft" | "approved" | "published" | "rejected";
  review_deadline: string | null;
  sanitizer_warnings: { pattern: string; excerpt: string }[];
  bookstack_page_id: number | null;
  bookstack_page_url: string | null;
  created_at: string;
  updated_at: string;
}

// ── Response types ────────────────────────────────────────────────────────────

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
  folder_id: string | null;
  is_shared: boolean;
  pinned: boolean;
  user_name: string | null;
  created_at: string;
  updated_at: string;
}

interface AssistantFolderResponse {
  id: string;
  name: string;
  color: string;
  is_team: boolean;
  min_role: string;
  user_id: string | null;
  created_at: string;
}

interface CapabilitiesResponse {
  openai_available: boolean;
  default_model: string;
}

// ── Mappers ───────────────────────────────────────────────────────────────────

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
    folderId: r.folder_id,
    isShared: r.is_shared,
    pinned: r.pinned,
    userName: r.user_name,
    createdAt: r.created_at,
    updatedAt: r.updated_at,
  };
}

function mapFolder(r: AssistantFolderResponse): AssistantFolder {
  return {
    id: r.id,
    name: r.name,
    color: r.color,
    isTeam: r.is_team,
    minRole: r.min_role ?? "analyst_n1",
    userId: r.user_id,
    createdAt: r.created_at,
  };
}

// ── API ───────────────────────────────────────────────────────────────────────

export const assistantApi = {
  // Capabilities
  capabilities: () =>
    apiClient.get<CapabilitiesResponse>("/assistant/capabilities").then((r) => r.data),

  // Chat
  chat: (data: {
    content: string;
    session_id?: string | null;
    model?: string | null;
    folder_id?: string | null;
  }) =>
    apiClient
      .post<AssistantMessageResponse>("/assistant/chat", {
        content: data.content,
        session_id: data.session_id ?? null,
        model: data.model ?? null,
        folder_id: data.folder_id ?? null,
      })
      .then((r) => mapMessage(r.data)),

  // Sessions
  listSessions: () =>
    apiClient
      .get<AssistantSessionResponse[]>("/assistant/sessions")
      .then((r) => r.data.map(mapSession)),

  listTeamSessions: () =>
    apiClient
      .get<AssistantSessionResponse[]>("/assistant/sessions/team")
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

  renameSession: (id: string, title: string) =>
    apiClient
      .put<AssistantSessionResponse>(`/assistant/sessions/${id}/rename`, { title })
      .then((r) => mapSession(r.data)),

  moveSession: (id: string, folderId: string | null) =>
    apiClient
      .put<AssistantSessionResponse>(`/assistant/sessions/${id}/move`, {
        folder_id: folderId,
      })
      .then((r) => mapSession(r.data)),

  shareSession: (id: string, shared: boolean) =>
    apiClient
      .put<AssistantSessionResponse>(`/assistant/sessions/${id}/share`, { shared })
      .then((r) => mapSession(r.data)),

  pinSession: (id: string, pinned: boolean) =>
    apiClient
      .put<AssistantSessionResponse>(`/assistant/sessions/${id}/pin`, { pinned })
      .then((r) => mapSession(r.data)),

  // Folders
  listFolders: () =>
    apiClient
      .get<AssistantFolderResponse[]>("/assistant/folders")
      .then((r) => r.data.map(mapFolder)),

  createFolder: (data: { name: string; color?: string; is_team: boolean; min_role?: string }) =>
    apiClient
      .post<AssistantFolderResponse>("/assistant/folders", data)
      .then((r) => mapFolder(r.data)),

  updateFolder: (id: string, data: { name?: string; color?: string }) =>
    apiClient
      .put<AssistantFolderResponse>(`/assistant/folders/${id}`, data)
      .then((r) => mapFolder(r.data)),

  deleteFolder: (id: string) =>
    apiClient.delete(`/assistant/folders/${id}`).then((r) => r.data),
};

// ── Doc drafts API ────────────────────────────────────────────────────────────

export const assistantDocsApi = {
  generateDoc: (sessionId: string) =>
    apiClient
      .post<DocDraft>(`/assistant/sessions/${sessionId}/generate-doc`)
      .then((r) => r.data),

  listDocs: (status?: string) =>
    apiClient
      .get<DocDraft[]>("/assistant/docs", { params: status ? { status } : undefined })
      .then((r) => r.data),

  getDoc: (id: string) =>
    apiClient.get<DocDraft>(`/assistant/docs/${id}`).then((r) => r.data),

  updateDoc: (id: string, data: { title?: string; content?: string }) =>
    apiClient.put<DocDraft>(`/assistant/docs/${id}`, data).then((r) => r.data),

  approveDoc: (id: string) =>
    apiClient.post<DocDraft>(`/assistant/docs/${id}/approve`).then((r) => r.data),

  rejectDoc: (id: string) =>
    apiClient.post<DocDraft>(`/assistant/docs/${id}/reject`).then((r) => r.data),

  publishDoc: (id: string) =>
    apiClient.post<DocDraft>(`/assistant/docs/${id}/publish`).then((r) => r.data),

  deleteDoc: (id: string) =>
    apiClient.delete(`/assistant/docs/${id}`).then((r) => r.data),
};
