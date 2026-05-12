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
  createdAt: string;
  updatedAt: string;
}

interface AssistantState {
  isOpen: boolean;
  currentSessionId: string | null;
  messages: AssistantMessage[];
  sessions: AssistantSession[];
  loading: boolean;
  selectedModel: "claude" | "openai";
  openaiAvailable: boolean;

  toggle: () => void;
  open: () => void;
  close: () => void;
  setModel: (m: "claude" | "openai") => void;
  setLoading: (v: boolean) => void;
  setOpenaiAvailable: (v: boolean) => void;
  addMessage: (msg: AssistantMessage) => void;
  setMessages: (msgs: AssistantMessage[]) => void;
  setSessions: (s: AssistantSession[]) => void;
  setCurrentSessionId: (id: string | null) => void;
  newSession: () => void;
}

export const useAssistantStore = create<AssistantState>((set) => ({
  isOpen: false,
  currentSessionId: null,
  messages: [],
  sessions: [],
  loading: false,
  selectedModel: "claude",
  openaiAvailable: false,

  toggle: () => set((s) => ({ isOpen: !s.isOpen })),
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  setModel: (m) => set({ selectedModel: m }),
  setLoading: (v) => set({ loading: v }),
  setOpenaiAvailable: (v) => set({ openaiAvailable: v }),
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  setMessages: (msgs) => set({ messages: msgs }),
  setSessions: (sessions) => set({ sessions }),
  setCurrentSessionId: (id) => set({ currentSessionId: id }),
  newSession: () => set({ currentSessionId: null, messages: [] }),
}));
