import { useEffect, useRef, useState } from "react";
import {
  Bot, Send, Loader2, Plus, Trash2, Sparkles, Database, MessageSquare,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { useAssistantStore, type AssistantMessage } from "../store/assistantStore";
import { assistantApi } from "../api/assistant";
import toast from "react-hot-toast";

// ── Bolha de mensagem ──────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: AssistantMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser ? "bg-brand-600" : "bg-gray-700"
        }`}
      >
        {isUser ? (
          <span className="text-white text-xs font-bold">U</span>
        ) : (
          <Bot size={15} className="text-white" />
        )}
      </div>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap break-words ${
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

// ── Página principal ───────────────────────────────────────────────────────────

export function AssistantPage() {
  const {
    currentSessionId, messages, sessions, loading, selectedModel, openaiAvailable,
    setModel, setLoading, setOpenaiAvailable, addMessage, setMessages,
    setSessions, setCurrentSessionId, newSession,
  } = useAssistantStore();

  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    assistantApi.capabilities()
      .then((c) => setOpenaiAvailable(c.openai_available))
      .catch(() => {});
    assistantApi.listSessions()
      .then((s) => setSessions(s))
      .catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

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
      });

      if (!currentSessionId) {
        setCurrentSessionId(aiMsg.sessionId);
        assistantApi.listSessions().then(setSessions).catch(() => {});
      }
      addMessage(aiMsg);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Erro ao comunicar com o assistente.";
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

  return (
    <PageWrapper
      title="Assistente IA"
      subtitle="Somente leitura · consulte dispositivos, compliance e operações em linguagem natural"
    >
      <div className="flex gap-4 h-[calc(100vh-140px)] min-h-0">

        {/* ── Coluna esquerda: sessões ─────────────────────────────────────── */}
        <div className="w-64 shrink-0 bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between shrink-0">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Sessões
            </span>
            <button
              onClick={() => newSession()}
              title="Nova sessão"
              className="text-gray-400 hover:text-brand-600 transition-colors"
            >
              <Plus size={16} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
            {sessions.length === 0 && (
              <p className="text-xs text-gray-400 text-center py-6 px-2">
                Nenhuma sessão anterior.
              </p>
            )}

            {/* Nova sessão (ativa quando sem sessão) */}
            {!currentSessionId && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-brand-50 text-brand-700 text-xs font-medium">
                <MessageSquare size={13} />
                <span className="flex-1 truncate">Nova sessão</span>
              </div>
            )}

            {sessions.map((s) => (
              <div
                key={s.id}
                onClick={() => loadSession(s.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-xs transition-colors group ${
                  s.id === currentSessionId
                    ? "bg-brand-50 text-brand-700"
                    : "hover:bg-gray-50 text-gray-600"
                }`}
              >
                <MessageSquare size={13} className="shrink-0 opacity-60" />
                <span className="flex-1 truncate">{s.title ?? "Sessão sem título"}</span>
                <button
                  onClick={(e) => deleteSession(s.id, e)}
                  className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-all shrink-0"
                >
                  <Trash2 size={11} />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* ── Coluna direita: chat ─────────────────────────────────────────── */}
        <div className="flex-1 bg-white rounded-xl border border-gray-200 flex flex-col min-w-0 overflow-hidden">

          {/* Header do chat */}
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <Sparkles size={15} className="text-brand-500" />
              <span className="text-sm font-semibold text-gray-800">
                {sessions.find((s) => s.id === currentSessionId)?.title ?? "Nova conversa"}
              </span>
            </div>
            {openaiAvailable && (
              <button
                onClick={() => setModel(selectedModel === "claude" ? "openai" : "claude")}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-600 transition-colors"
              >
                <Bot size={12} />
                Modelo: {selectedModel === "claude" ? "Claude" : "GPT-4o"}
              </button>
            )}
          </div>

          {/* Mensagens */}
          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4 min-h-0">
            {messages.length === 0 && (
              <div className="text-center text-gray-400 mt-20 select-none">
                <Sparkles size={40} className="mx-auto mb-3 opacity-20" />
                <p className="font-medium text-base">Como posso ajudar?</p>
                <p className="text-sm mt-1 text-gray-300 max-w-sm mx-auto">
                  Pergunte sobre dispositivos, compliance, operações recentes ou boas práticas de segurança.
                </p>
              </div>
            )}
            {messages.map((msg) => (
              <MessageBubble key={msg.id} msg={msg} />
            ))}
            {loading && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center shrink-0">
                  <Bot size={15} className="text-white" />
                </div>
                <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3">
                  <Loader2 size={15} className="animate-spin text-gray-500" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="px-5 py-4 border-t border-gray-100 shrink-0">
            <div className="flex gap-3">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Pergunte sobre sua infraestrutura… (Enter para enviar, Shift+Enter para nova linha)"
                disabled={loading}
                rows={2}
                className="flex-1 text-sm border border-gray-200 rounded-xl px-4 py-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-gray-50"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || loading}
                className="self-end w-10 h-10 bg-brand-600 hover:bg-brand-700 text-white rounded-xl flex items-center justify-center disabled:opacity-40 transition-colors shrink-0"
              >
                <Send size={16} />
              </button>
            </div>
            <p className="text-[11px] text-gray-400 mt-2">
              Este assistente não executa operações.
              {openaiAvailable && (
                <> Modelo ativo: <strong>{selectedModel === "openai" ? "GPT-4o" : "Claude"}</strong>.</>
              )}
            </p>
          </div>
        </div>
      </div>
    </PageWrapper>
  );
}
