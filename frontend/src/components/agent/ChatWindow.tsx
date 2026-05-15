import { useEffect, useRef, useState } from "react";
import { Send, Loader2, Mic, MicOff, Paperclip, X } from "lucide-react";
import type { ChatMessage, ClarificationQuestion } from "../../store/agentStore";
import type { Attachment, DiagnosticAnalysis } from "../../types/operation";
import { operationsApi } from "../../api/operations";
import { MessageBubble } from "./MessageBubble";
import { ActionPlanCard } from "./ActionPlanCard";
import { ClarificationCard } from "./ClarificationCard";
import { DiagnosticPanel } from "./DiagnosticPanel";
import { useSpeechRecognition } from "../../hooks/useSpeechRecognition";

const ACCEPTED_FILE_TYPES = ".txt,.log,.conf,.csv,.md,.pdf,.json,.yaml,.yml";
const MAX_TEXT_FILE_SIZE = 5 * 1024 * 1024; // 5 MB

interface ChatWindowProps {
  messages: ChatMessage[];
  readyToExecute: boolean;
  requiresApproval: boolean;
  loading: boolean;
  onSend: (message: string, attachment?: Attachment) => void;
  onExecute: () => void;
  onSubmitForReview: () => void;
  onCancel: () => void;
  defaultInput?: string;
  // Clarification loop (Fase 40-A)
  clarifying?: boolean;
  clarificationQuestions?: ClarificationQuestion[];
  onSubmitClarification?: (answers: { id: string; answer: string }[]) => void;
  confidenceScore?: number | null;
  // Diagnostic panel (interactive get_info follow-up)
  diagnosticResult?: DiagnosticAnalysis | null;
  onRunDiagnosticCommand?: (cmd: string) => void;
  onClearDiagnostic?: () => void;
  onDiagnosticFollowUp?: (message: string) => Promise<string>;
}

export function ChatWindow({
  messages,
  readyToExecute,
  requiresApproval,
  loading,
  onSend,
  onExecute,
  onSubmitForReview,
  onCancel,
  defaultInput,
  clarifying = false,
  clarificationQuestions = [],
  onSubmitClarification,
  confidenceScore,
  diagnosticResult,
  onRunDiagnosticCommand,
  onClearDiagnostic,
  onDiagnosticFollowUp,
}: ChatWindowProps) {
  const [input, setInput] = useState(defaultInput ?? "");
  const [attachment, setAttachment] = useState<Attachment | null>(null);
  const [attachLoading, setAttachLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Speech recognition: sets the transcript into the input field
  const { mode: speechMode, start: startSpeech, stop: stopSpeech } = useSpeechRecognition(
    (text) => setInput((prev) => (prev ? `${prev} ${text}` : text))
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if ((!input.trim() && !attachment) || loading) return;
    onSend(input.trim(), attachment ?? undefined);
    setInput("");
    setAttachment(null);
  };

  const handleRunDiagnosticCommand = (cmd: string) => {
    if (onRunDiagnosticCommand) {
      onRunDiagnosticCommand(cmd);
    } else {
      setInput(cmd);
    }
  };

  // File processing: converts file to Attachment
  const processFile = async (file: File): Promise<Attachment | null> => {
    const isImage = file.type.startsWith("image/");
    if (isImage) {
      return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => {
          const dataUrl = e.target?.result as string;
          // dataUrl is "data:image/png;base64,..."
          const base64 = dataUrl.split(",")[1];
          resolve({ type: "image", data: base64, filename: file.name, mime_type: file.type });
        };
        reader.readAsDataURL(file);
      });
    }

    // PDF: send to backend for extraction
    if (file.name.toLowerCase().endsWith(".pdf")) {
      const result = await operationsApi.parseFile(file);
      return { type: "text", data: result.text, filename: file.name, mime_type: "text/plain" };
    }

    // Text file: read directly in browser
    if (file.size > MAX_TEXT_FILE_SIZE) {
      return null;
    }
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = (e.target?.result as string) ?? "";
        resolve({ type: "text", data: text.slice(0, 10000), filename: file.name, mime_type: "text/plain" });
      };
      reader.readAsText(file, "utf-8");
    });
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // Reset input so same file can be re-selected
    e.target.value = "";
    setAttachLoading(true);
    try {
      const att = await processFile(file);
      if (att) setAttachment(att);
    } catch {
      // silently ignore — user can try again
    } finally {
      setAttachLoading(false);
    }
  };

  const micDisabled = loading || readyToExecute || clarifying;
  const inputDisabled = loading || readyToExecute || clarifying;
  const sendDisabled = loading || (!input.trim() && !attachment) || readyToExecute || clarifying;

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !diagnosticResult && (
          <div className="text-center text-gray-400 mt-16">
            <p className="text-lg mb-2">Olá! Sou o FireManager AI.</p>
            <p className="text-sm">Descreva o que você precisa fazer no firewall selecionado.</p>
            <p className="text-xs mt-2">Exemplo: "Liberar porta 443 para o servidor 10.0.0.5"</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="h-8 w-8 rounded-full bg-gray-700 flex items-center justify-center">
              <Loader2 size={16} className="text-white animate-spin" />
            </div>
            <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3">
              <span className="text-sm text-gray-500">Processando...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Diagnostic panel — rendered above input, persists across new operations */}
      {diagnosticResult && onDiagnosticFollowUp && onClearDiagnostic && (
        <div className="px-4 pb-2">
          <DiagnosticPanel
            analysis={diagnosticResult}
            onRunCommand={handleRunDiagnosticCommand}
            onClose={onClearDiagnostic}
            onFollowUp={onDiagnosticFollowUp}
          />
        </div>
      )}

      {clarifying && clarificationQuestions.length > 0 && onSubmitClarification && (
        <ClarificationCard
          questions={clarificationQuestions}
          onSubmit={onSubmitClarification}
          loading={loading}
        />
      )}

      {readyToExecute && (
        <div className="px-4 pb-2">
          {confidenceScore !== null && confidenceScore !== undefined && (
            <div className="mb-2 flex items-center gap-1.5 text-xs text-gray-500">
              <span>Confiança do agente:</span>
              <span
                className={`font-semibold ${
                  confidenceScore >= 0.8
                    ? "text-green-600"
                    : confidenceScore >= 0.65
                    ? "text-yellow-600"
                    : "text-red-600"
                }`}
              >
                {Math.round(confidenceScore * 100)}%
              </span>
            </div>
          )}
          <ActionPlanCard
            requiresApproval={requiresApproval}
            onConfirm={onExecute}
            onSubmitForReview={onSubmitForReview}
            onCancel={onCancel}
            loading={loading}
          />
        </div>
      )}

      {/* Attachment preview bar */}
      {attachment && (
        <div className="px-4 pb-1">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-brand-50 border border-brand-200 rounded-lg text-xs text-brand-700">
            {attachment.type === "image" ? (
              <img
                src={`data:${attachment.mime_type};base64,${attachment.data}`}
                alt={attachment.filename}
                className="h-8 w-8 object-cover rounded border border-brand-300 shrink-0"
              />
            ) : (
              <Paperclip size={13} className="shrink-0 text-brand-500" />
            )}
            <span className="truncate flex-1">{attachment.filename}</span>
            <button
              onClick={() => setAttachment(null)}
              className="shrink-0 text-brand-400 hover:text-brand-600"
              title="Remover anexo"
            >
              <X size={13} />
            </button>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-200">
        <div className="flex gap-2">
          {/* Mic button */}
          <button
            type="button"
            onClick={speechMode === "idle" ? startSpeech : stopSpeech}
            disabled={micDisabled || speechMode === "processing"}
            title={speechMode === "recording" ? "Parar gravação" : "Gravar voz"}
            className={`flex-none flex items-center justify-center w-10 h-10 rounded-xl border transition-colors disabled:opacity-40 ${
              speechMode === "recording"
                ? "bg-red-500 border-red-500 text-white animate-pulse"
                : speechMode === "processing"
                ? "bg-gray-100 border-gray-300 text-gray-400"
                : "bg-white border-gray-300 text-gray-500 hover:border-brand-400 hover:text-brand-600"
            }`}
          >
            {speechMode === "processing" ? (
              <Loader2 size={16} className="animate-spin" />
            ) : speechMode === "recording" ? (
              <MicOff size={16} />
            ) : (
              <Mic size={16} />
            )}
          </button>

          {/* File attach button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={inputDisabled || attachLoading}
            title="Anexar arquivo ou imagem"
            className="flex-none flex items-center justify-center w-10 h-10 rounded-xl border border-gray-300 bg-white text-gray-500 hover:border-brand-400 hover:text-brand-600 transition-colors disabled:opacity-40"
          >
            {attachLoading ? <Loader2 size={16} className="animate-spin" /> : <Paperclip size={16} />}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept={`${ACCEPTED_FILE_TYPES},image/*`}
            className="hidden"
            onChange={handleFileChange}
          />

          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              speechMode === "recording"
                ? "Ouvindo…"
                : "Descreva a operação desejada..."
            }
            className="flex-1 border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            disabled={inputDisabled}
          />
          <button
            type="submit"
            disabled={sendDisabled}
            className="bg-brand-600 text-white rounded-xl px-4 py-2.5 hover:bg-brand-700 disabled:opacity-50 transition-colors"
          >
            <Send size={18} />
          </button>
        </div>
      </form>
    </div>
  );
}
