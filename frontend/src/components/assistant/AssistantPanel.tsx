import { useEffect, useRef, useState } from "react";
import {
  Bot, X, Send, Loader2, Plus, Trash2, ChevronDown, Sparkles, Database, FileText,
  Globe, Shield,
} from "lucide-react";
import { useAssistantStore, type AssistantMessage } from "../../store/assistantStore";
import { assistantApi, assistantDocsApi, type DocDraft } from "../../api/assistant";
import { useAuthStore } from "../../store/authStore";
import { useLocation } from "react-router-dom";
import toast from "react-hot-toast";
import { DocDraftModal } from "./DocDraftModal";
import { DocTypeSelector } from "./DocTypeSelector";

// ── Bolha de mensagem ─────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: AssistantMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-2 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
          isUser ? "bg-brand-600" : "bg-gray-700"
        }`}
      >
        {isUser ? (
          <span className="text-white text-xs font-bold">U</span>
        ) : (
          <Bot size={14} className="text-white" />
        )}
      </div>
      <div
        className={`max-w-[82%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap break-words ${
          isUser
            ? "bg-brand-600 text-white rounded-tr-sm"
            : "bg-gray-100 text-gray-900 rounded-tl-sm"
        }`}
      >
        {msg.content}
        {!isUser && (
          <div className="mt-1.5 flex items-center gap-2 flex-wrap">
            {msg.model && (
              <span className="text-[10px] text-gray-400 font-medium">{msg.model}</span>
            )}
            {msg.ragContextUsed && (
              <span className="flex items-center gap-0.5 text-[10px] text-blue-500">
                <Database size={9} />
                RAG
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Painel principal ──────────────────────────────────────────────────────────

export function AssistantPanel() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const location = useLocation();
  const skip =
    !isAuthenticated ||
    ["/login", "/invite"].some((p) => location.pathname.startsWith(p));
  if (skip) return null;
  return <AssistantPanelInner />;
}

function AssistantPanelInner() {
  const {
    isOpen, currentSessionId, messages, sessions, loading, selectedModel, openaiAvailable,
    chatMode, close, setModel, setChatMode, setLoading, setOpenaiAvailable, addMessage, setMessages,
    setSessions, setCurrentSessionId, newSession,
  } = useAssistantStore();

  const [input, setInput] = useState("");
  const [showSessions, setShowSessions] = useState(false);
  const [generatingDoc, setGeneratingDoc] = useState(false);
  const [showDocTypeSelector, setShowDocTypeSelector] = useState(false);
  const [docDraft, setDocDraft] = useState<DocDraft | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Carregar capabilities e sessões ao abrir
  useEffect(() => {
    if (!isOpen) return;
    assistantApi.capabilities()
      .then((c) => setOpenaiAvailable(c.openai_available))
      .catch(() => {});
    assistantApi.listSessions()
      .then((s) => setSessions(s))
      .catch(() => {});
  }, [isOpen]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    // Adiciona msg do usuário imediatamente
    const userMsg: AssistantMessage = {
      id: `user-${Date.now()}`,
      sessionId: currentSessionId ?? "",
      role: "user",
      content: text,
      ragContextUsed: false,
      createdAt: new Date().toISOString(),
    };
    addMessage(userMsg);
    setInput("");
    setLoading(true);

    try {
      const aiMsg = await assistantApi.chat({
        content: text,
        session_id: currentSessionId,
        model: selectedModel === "openai" ? "openai" : null,
        mode: chatMode,
      });

      // Atualizar session_id se era nova sessão
      if (!currentSessionId) {
        setCurrentSessionId(aiMsg.sessionId);
        // Recarregar lista de sessões
        assistantApi.listSessions().then(setSessions).catch(() => {});
      }
      addMessage(aiMsg);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "Erro ao comunicar com o assistant.";
      toast.error(msg);
      addMessage({
        id: `err-${Date.now()}`,
        sessionId: currentSessionId ?? "",
        role: "assistant",
        content: "Desculpe, ocorreu um erro. Tente novamente.",
        ragContextUsed: false,
        createdAt: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const loadSession = async (id: string) => {
    setShowSessions(false);
    setLoading(true);
    try {
      const { session, messages: msgs } = await assistantApi.getSession(id);
      setCurrentSessionId(session.id);
      setMessages(msgs);
    } catch {
      toast.error("Erro ao carregar sessão.");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateDoc = async (docType: string) => {
    if (!currentSessionId || generatingDoc) return;
    setShowDocTypeSelector(false);
    setGeneratingDoc(true);
    try {
      const draft = await assistantDocsApi.generateDoc(currentSessionId, docType);
      setDocDraft(draft);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Erro ao gerar documentação.";
      toast.error(msg);
    } finally {
      setGeneratingDoc(false);
    }
  };

  const deleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await assistantApi.deleteSession(id);
      setSessions(sessions.filter((s) => s.id !== id));
      if (currentSessionId === id) newSession();
      toast.success("Sessão removida.");
    } catch {
      toast.error("Erro ao remover sessão.");
    }
  };

  if (!isOpen) return null;

  return (
    <>
    {showDocTypeSelector && (
      <DocTypeSelector
        onSelect={handleGenerateDoc}
        onClose={() => setShowDocTypeSelector(false)}
      />
    )}
    {docDraft && (
      <DocDraftModal
        draft={docDraft}
        onClose={() => setDocDraft(null)}
        onUpdated={(updated) => setDocDraft(updated)}
      />
    )}
    <div className="fixed right-0 top-0 h-full w-[420px] bg-white shadow-2xl z-40 flex flex-col border-l border-gray-200">

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-900 text-white shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <Sparkles size={16} className="text-brand-400 shrink-0" />
          <div className="min-w-0">
            <p className="text-sm font-semibold leading-tight">AI Assistant</p>
            <p className="text-[10px] text-gray-400">Somente leitura · não executa operações</p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          {/* Mode selector dropdown */}
          <div className="relative">
            <select
              value={chatMode}
              onChange={(e) => setChatMode(e.target.value as "infrastructure" | "general")}
              className={`appearance-none text-[10px] pl-5 pr-4 py-1 rounded cursor-pointer focus:outline-none transition-colors ${
                chatMode === "general"
                  ? "bg-purple-700 border border-purple-500 text-purple-100"
                  : "bg-gray-800 border border-gray-600 text-gray-300 hover:bg-gray-700"
              }`}
            >
              <option value="infrastructure">Infraestrutura</option>
              <option value="general">Tecnologia Geral</option>
            </select>
            <span className="pointer-events-none absolute left-1 top-1/2 -translate-y-1/2">
              {chatMode === "general" ? <Globe size={9} className="text-purple-200" /> : <Shield size={9} className="text-gray-400" />}
            </span>
          </div>
          {/* Seletor de modelo (apenas se OpenAI disponível) */}
          {openaiAvailable && (
            <button
              onClick={() => setModel(selectedModel === "claude" ? "openai" : "claude")}
              title="Alternar modelo"
              className="flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
            >
              <Bot size={10} />
              {selectedModel === "claude" ? "Claude" : "GPT-4o"}
            </button>
          )}
          {currentSessionId && messages.length > 0 && (
            <button
              onClick={() => setShowDocTypeSelector(true)}
              disabled={generatingDoc}
              title="Gerar documentação desta sessão"
              className="flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-gray-800 hover:bg-brand-600 text-gray-300 hover:text-white disabled:opacity-50 transition-colors"
            >
              {generatingDoc ? (
                <Loader2 size={10} className="animate-spin" />
              ) : (
                <FileText size={10} />
              )}
              {generatingDoc ? "Gerando…" : "Documentar"}
            </button>
          )}
          <button onClick={close} className="text-gray-400 hover:text-white transition-colors">
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Sessões */}
      <div className="px-4 py-2 border-b border-gray-100 bg-gray-50 shrink-0">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSessions(!showSessions)}
            className="flex-1 flex items-center justify-between text-xs text-gray-600 hover:text-gray-800 transition-colors"
          >
            <span className="truncate">
              {sessions.find((s) => s.id === currentSessionId)?.title ?? "Nova sessão"}
            </span>
            <ChevronDown
              size={13}
              className={`shrink-0 transition-transform ${showSessions ? "rotate-180" : ""}`}
            />
          </button>
          <button
            onClick={() => { newSession(); setShowSessions(false); }}
            title="Nova sessão"
            className="text-gray-400 hover:text-brand-600 transition-colors"
          >
            <Plus size={15} />
          </button>
        </div>

        {showSessions && (
          <div className="mt-2 max-h-48 overflow-y-auto space-y-1">
            {sessions.length === 0 && (
              <p className="text-xs text-gray-400 py-2">Nenhuma sessão anterior.</p>
            )}
            {sessions.map((s) => (
              <div
                key={s.id}
                onClick={() => loadSession(s.id)}
                className={`flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer text-xs transition-colors group ${
                  s.id === currentSessionId
                    ? "bg-brand-50 text-brand-700"
                    : "hover:bg-gray-100 text-gray-700"
                }`}
              >
                <span className="flex-1 truncate">{s.title ?? "Sessão sem título"}</span>
                <button
                  onClick={(e) => deleteSession(s.id, e)}
                  className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-all"
                >
                  <Trash2 size={11} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Mensagens */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 text-sm mt-12 select-none">
            <Sparkles size={32} className="mx-auto mb-2 opacity-20" />
            <p className="font-medium">Como posso ajudar?</p>
            <p className="text-xs mt-1 text-gray-300">
              Pergunte sobre dispositivos, compliance, operações recentes ou boas práticas.
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
        {loading && (
          <div className="flex gap-2">
            <div className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center shrink-0">
              <Bot size={14} className="text-white" />
            </div>
            <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-3 py-2">
              <Loader2 size={14} className="animate-spin text-gray-500" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-gray-200 shrink-0">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Pergunte sobre sua infraestrutura… (Enter para enviar)"
            disabled={loading}
            rows={2}
            className="flex-1 text-sm border border-gray-200 rounded-xl px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-gray-50"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="self-end w-9 h-9 bg-brand-600 hover:bg-brand-700 text-white rounded-xl flex items-center justify-center disabled:opacity-40 transition-colors shrink-0"
          >
            <Send size={15} />
          </button>
        </div>
        <p className="text-[10px] text-gray-400 mt-1.5 text-center">
          Este assistente não executa operações.
          {openaiAvailable && (
            <> Modelo: <strong>{selectedModel === "openai" ? "GPT-4o" : "Claude"}</strong>.</>
          )}
        </p>
      </div>
    </div>
    </>
  );
}
