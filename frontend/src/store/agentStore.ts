import { create } from "zustand";

export interface TableColumn {
  key: string;
  label: string;
}

export interface TableData {
  columns: TableColumn[];
  rows: Record<string, unknown>[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  tableData?: TableData;
  timestamp: Date;
}

interface AgentState {
  messages: ChatMessage[];
  currentOperationId: string | null;
  readyToExecute: boolean;
  loading: boolean;
  addMessage: (role: "user" | "assistant", content: string, tableData?: TableData) => void;
  setOperationId: (id: string | null) => void;
  setReadyToExecute: (ready: boolean) => void;
  setLoading: (loading: boolean) => void;
  // Resets only the active operation state — keeps messages visible
  resetSession: () => void;
  // Resets everything including messages (use when switching devices)
  reset: () => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  messages: [],
  currentOperationId: null,
  readyToExecute: false,
  loading: false,

  addMessage: (role, content, tableData?) =>
    set((state) => ({
      messages: [...state.messages, { role, content, tableData, timestamp: new Date() }],
    })),

  setOperationId: (id) => set({ currentOperationId: id }),
  setReadyToExecute: (ready) => set({ readyToExecute: ready }),
  setLoading: (loading) => set({ loading }),

  resetSession: () =>
    set({ currentOperationId: null, readyToExecute: false, loading: false }),

  reset: () =>
    set({ messages: [], currentOperationId: null, readyToExecute: false, loading: false }),
}));
