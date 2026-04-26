import { useEffect, useRef, useState } from "react";
import { Send, Loader2 } from "lucide-react";
import type { ChatMessage } from "../../store/agentStore";
import { MessageBubble } from "./MessageBubble";
import { ActionPlanCard } from "./ActionPlanCard";

interface ChatWindowProps {
  messages: ChatMessage[];
  readyToExecute: boolean;
  requiresApproval: boolean;
  loading: boolean;
  onSend: (message: string) => void;
  onExecute: () => void;
  onSubmitForReview: () => void;
  onCancel: () => void;
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
}: ChatWindowProps) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    onSend(input.trim());
    setInput("");
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
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

      {readyToExecute && (
        <div className="px-4 pb-2">
          <ActionPlanCard
            requiresApproval={requiresApproval}
            onConfirm={onExecute}
            onSubmitForReview={onSubmitForReview}
            onCancel={onCancel}
            loading={loading}
          />
        </div>
      )}

      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-200">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Descreva a operação desejada..."
            className="flex-1 border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            disabled={loading || readyToExecute}
          />
          <button
            type="submit"
            disabled={loading || !input.trim() || readyToExecute}
            className="bg-brand-600 text-white rounded-xl px-4 py-2.5 hover:bg-brand-700 disabled:opacity-50 transition-colors"
          >
            <Send size={18} />
          </button>
        </div>
      </form>
    </div>
  );
}
