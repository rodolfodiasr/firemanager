import { create } from "zustand";

export interface AssistantMessage {
  id: string;
  sessionId: string;
  role: "user" | "assistant";
  content: string;
  model?: string | null;
  inputTokens?: number | null;
  outputTokens?: number | null;
  ragContextUsed: boolean;
  createdAt: string;
}

export interface AssistantSession {
  id: string;
  title?: string | null;
  modelUsed: string;
  messageCount: number;
  folderId?: string | null;
  isShared: boolean;
  pinned: boolean;
  userName?: string | null;
  glpiTicketId?: number | null;
  glpiIntegrationId?: string | null;
  glpiItemtype?: string | null;
  glpiTicketTitle?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface AssistantFolder {
  id: string;
  name: string;
  color: string;
  isTeam: boolean;
  minRole: string;
  userId: string | null;
  createdAt: string;
}

interface AssistantState {
  isOpen: boolean;
  currentSessionId: string | null;
  messages: AssistantMessage[];
  sessions: AssistantSession[];
  teamSessions: AssistantSession[];
  folders: AssistantFolder[];
  loading: boolean;
  selectedModel: "claude" | "openai";
  openaiAvailable: boolean;
  chatMode: "infrastructure" | "general" | "platform";

  toggle: () => void;
  open: () => void;
  close: () => void;
  setModel: (m: "claude" | "openai") => void;
  setChatMode: (m: "infrastructure" | "general" | "platform") => void;
  setLoading: (v: boolean) => void;
  setOpenaiAvailable: (v: boolean) => void;
  addMessage: (msg: AssistantMessage) => void;
  setMessages: (msgs: AssistantMessage[]) => void;
  setSessions: (s: AssistantSession[]) => void;
  setTeamSessions: (s: AssistantSession[]) => void;
  setFolders: (f: AssistantFolder[]) => void;
  setCurrentSessionId: (id: string | null) => void;
  newSession: () => void;

  // Mutações locais (otimistas)
  updateSession: (id: string, patch: Partial<AssistantSession>) => void;
  removeSession: (id: string) => void;
  addFolder: (f: AssistantFolder) => void;
  updateFolder: (id: string, patch: Partial<AssistantFolder>) => void;
  removeFolder: (id: string) => void;
}

export const useAssistantStore = create<AssistantState>((set) => ({
  isOpen: false,
  currentSessionId: null,
  messages: [],
  sessions: [],
  teamSessions: [],
  folders: [],
  loading: false,
  selectedModel: "claude",
  openaiAvailable: false,
  chatMode: "infrastructure",

  toggle: () => set((s) => ({ isOpen: !s.isOpen })),
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  setModel: (m) => set({ selectedModel: m }),
  setChatMode: (m) => set({ chatMode: m }),
  setLoading: (v) => set({ loading: v }),
  setOpenaiAvailable: (v) => set({ openaiAvailable: v }),
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  setMessages: (msgs) => set({ messages: msgs }),
  setSessions: (sessions) => set({ sessions }),
  setTeamSessions: (teamSessions) => set({ teamSessions }),
  setFolders: (folders) => set({ folders }),
  setCurrentSessionId: (id) => set({ currentSessionId: id }),
  newSession: () => set({ currentSessionId: null, messages: [] }),

  updateSession: (id, patch) =>
    set((s) => ({
      sessions: s.sessions.map((x) => (x.id === id ? { ...x, ...patch } : x)),
      teamSessions: s.teamSessions.map((x) => (x.id === id ? { ...x, ...patch } : x)),
    })),
  removeSession: (id) =>
    set((s) => ({
      sessions: s.sessions.filter((x) => x.id !== id),
      teamSessions: s.teamSessions.filter((x) => x.id !== id),
      currentSessionId: s.currentSessionId === id ? null : s.currentSessionId,
      messages: s.currentSessionId === id ? [] : s.messages,
    })),
  addFolder: (f) => set((s) => ({ folders: [...s.folders, f] })),
  updateFolder: (id, patch) =>
    set((s) => ({
      folders: s.folders.map((x) => (x.id === id ? { ...x, ...patch } : x)),
    })),
  removeFolder: (id) =>
    set((s) => ({
      folders: s.folders.filter((x) => x.id !== id),
      sessions: s.sessions.map((x) =>
        x.folderId === id ? { ...x, folderId: null } : x
      ),
    })),
}));
