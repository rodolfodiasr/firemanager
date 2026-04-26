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
  requiresApproval: boolean;
  intent: string | null;
  loading: boolean;
  addMessage: (role: "user" | "assistant", content: string, tableData?: TableData) => void;
  setOperationId: (id: string | null) => void;
  setReadyToExecute: (ready: boolean) => void;
  setRequiresApproval: (v: boolean) => void;
  setIntent: (v: string | null) => void;
  setLoading: (loading: boolean) => void;
  resetSession: () => void;
  reset: () => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  messages: [],
  currentOperationId: null,
  readyToExecute: false,
  requiresApproval: false,
  intent: null,
  loading: false,

  addMessage: (role, content, tableData?) =>
    set((state) => ({
      messages: [...state.messages, { role, content, tableData, timestamp: new Date() }],
    })),

  setOperationId: (id) => set({ currentOperationId: id }),
  setReadyToExecute: (ready) => set({ readyToExecute: ready }),
  setRequiresApproval: (v) => set({ requiresApproval: v }),
  setIntent: (v) => set({ intent: v }),
  setLoading: (loading) => set({ loading }),

  resetSession: () =>
    set({ currentOperationId: null, readyToExecute: false, requiresApproval: false, intent: null, loading: false }),

  reset: () =>
    set({ messages: [], currentOperationId: null, readyToExecute: false, requiresApproval: false, intent: null, loading: false }),
}));
