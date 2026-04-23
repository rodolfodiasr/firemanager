import { create } from "zustand";
import type { ChatResponse } from "../types/operation";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface AgentState {
  messages: ChatMessage[];
  currentOperationId: string | null;
  readyToExecute: boolean;
  loading: boolean;
  addMessage: (role: "user" | "assistant", content: string) => void;
  setOperationId: (id: string | null) => void;
  setReadyToExecute: (ready: boolean) => void;
  setLoading: (loading: boolean) => void;
  reset: () => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  messages: [],
  currentOperationId: null,
  readyToExecute: false,
  loading: false,

  addMessage: (role, content) =>
    set((state) => ({
      messages: [...state.messages, { role, content, timestamp: new Date() }],
    })),

  setOperationId: (id) => set({ currentOperationId: id }),
  setReadyToExecute: (ready) => set({ readyToExecute: ready }),
  setLoading: (loading) => set({ loading }),

  reset: () =>
    set({ messages: [], currentOperationId: null, readyToExecute: false, loading: false }),
}));
