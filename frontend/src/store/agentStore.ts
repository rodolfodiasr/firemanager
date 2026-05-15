import { create } from "zustand";
import type { DiagnosticAnalysis } from "../types/operation";

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
  directModeDeviceId?: string;
}

export interface ClarificationQuestion {
  id: string;
  question: string;
  field: string;
  options?: string[];
}

interface AgentState {
  messages: ChatMessage[];
  currentOperationId: string | null;
  readyToExecute: boolean;
  requiresApproval: boolean;
  intent: string | null;
  loading: boolean;
  // Clarification loop (Fase 40-A)
  clarifying: boolean;
  clarificationQuestions: ClarificationQuestion[];
  confidenceScore: number | null;
  // Diagnostic panel state — intentionally NOT cleared by resetSession
  diagnosticResult: DiagnosticAnalysis | null;
  diagnosticOperationId: string | null;
  addMessage: (role: "user" | "assistant", content: string, tableData?: TableData, directModeDeviceId?: string) => void;
  setOperationId: (id: string | null) => void;
  setReadyToExecute: (ready: boolean) => void;
  setRequiresApproval: (v: boolean) => void;
  setIntent: (v: string | null) => void;
  setLoading: (loading: boolean) => void;
  setClarifying: (clarifying: boolean, questions?: ClarificationQuestion[]) => void;
  setConfidenceScore: (score: number | null) => void;
  setDiagnosticResult: (result: DiagnosticAnalysis | null, opId: string | null) => void;
  clearDiagnosticResult: () => void;
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
  clarifying: false,
  clarificationQuestions: [],
  confidenceScore: null,
  diagnosticResult: null,
  diagnosticOperationId: null,

  addMessage: (role, content, tableData?, directModeDeviceId?) =>
    set((state) => ({
      messages: [...state.messages, { role, content, tableData, directModeDeviceId, timestamp: new Date() }],
    })),

  setOperationId: (id) => set({ currentOperationId: id }),
  setReadyToExecute: (ready) => set({ readyToExecute: ready }),
  setRequiresApproval: (v) => set({ requiresApproval: v }),
  setIntent: (v) => set({ intent: v }),
  setLoading: (loading) => set({ loading }),
  setClarifying: (clarifying, questions = []) =>
    set({ clarifying, clarificationQuestions: questions }),
  setConfidenceScore: (score) => set({ confidenceScore: score }),
  setDiagnosticResult: (result, opId) =>
    set({ diagnosticResult: result, diagnosticOperationId: opId }),
  clearDiagnosticResult: () =>
    set({ diagnosticResult: null, diagnosticOperationId: null }),

  // resetSession clears the operation flow but intentionally preserves diagnosticResult
  resetSession: () =>
    set({
      currentOperationId: null,
      readyToExecute: false,
      requiresApproval: false,
      intent: null,
      loading: false,
      clarifying: false,
      clarificationQuestions: [],
      confidenceScore: null,
    }),

  reset: () =>
    set({
      messages: [],
      currentOperationId: null,
      readyToExecute: false,
      requiresApproval: false,
      intent: null,
      loading: false,
      clarifying: false,
      clarificationQuestions: [],
      confidenceScore: null,
      diagnosticResult: null,
      diagnosticOperationId: null,
    }),
}));
