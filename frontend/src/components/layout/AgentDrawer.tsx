import { useState, useRef, useEffect, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Bot,
  X,
  Send,
  Maximize2,
  Loader2,
  ChevronDown,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { useDevices } from "../../hooks/useDevices";
import { operationsApi } from "../../api/operations";

const ROUTE_LABEL: Record<string, string> = {
  "/": "Dashboard",
  "/devices": "Dispositivos",
  "/inspector": "Inspetor",
  "/direct-mode": "CLI Direto",
  "/golden-templates": "Templates",
  "/golden-bundles": "Kits · Bundles",
  "/firewall-migrations": "Importar Regras",
  "/connectivity": "Topologia & Rotas",
  "/migrations": "Migração de Switches",
  "/servers": "Servidores",
  "/server-analysis": "Agente N3",
  "/server-direct": "Console SSH",
  "/database-connectors": "Bancos de Dados",
  "/vm-migration": "Migração de VMs",
  "/identity": "Identidade & Acesso",
  "/onboarding": "Onboarding",
  "/agent": "Agente de Firewall",
  "/network-agent": "Agente de Redes",
  "/knowledge": "Base de Conhecimento",
  "/compliance": "Conformidade",
  "/governance": "Governança",
  "/alerts": "Alertas",
  "/remediation": "Remediações",
  "/executive": "Dashboard Executivo",
  "/glpi": "Tickets IA",
  "/audit": "Auditoria",
  "/enterprise": "Enterprise",
  "/settings": "Configurações",
  "/organization": "Organização",
  "/mssp": "Painel MSSP",
  "/platform-config": "Config. de Plataforma",
};

// Páginas que pertencem ao domínio de redes (switches/roteadores)
const NETWORK_PATHS = ["/connectivity", "/migrations", "/network-agent"];

interface Message {
  role: "user" | "assistant";
  content: string;
}

// Wrapper: decide se monta o drawer (não chama nenhum hook de dados)
export function AgentDrawer() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const location = useLocation();
  const skip = !isAuthenticated || ["/login", "/invite"].some((p) => location.pathname.startsWith(p));
  if (skip) return null;
  return <AgentDrawerInner />;
}

// Inner: todos os hooks e lógica — só monta quando autenticado e fora do /login
function AgentDrawerInner() {
  const location = useLocation();
  const contextLabel = ROUTE_LABEL[location.pathname] ?? "Página atual";

  // Detecta contexto: rede ou firewall
  const isNetworkContext = NETWORK_PATHS.some((p) => location.pathname.startsWith(p));
  const agentLabel = isNetworkContext ? "Agente de Redes" : "Agente de Firewall";
  const agentPath = isNetworkContext ? "/network-agent" : "/agent";
  const agentPlaceholderExample = isNetworkContext
    ? "Ex: "Liste as VLANs configuradas""
    : "Ex: "Liste as regras de firewall"";

  const [isOpen, setIsOpen] = useState(false);
  const [deviceId, setDeviceId] = useState("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [operationId, setOperationId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { devices: allDevices } = useDevices();

  // Filtra devices pelo domínio atual
  const devices = allDevices.filter((d) =>
    isNetworkContext
      ? d.category === "switch" || d.category === "routing"
      : d.category === "firewall"
  );

  // Quando muda de contexto (rede ↔ firewall), limpa seleção e conversa
  useEffect(() => {
    setDeviceId("");
    setMessages([]);
    setOperationId(null);
  }, [isNetworkContext]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const resetConversation = useCallback(() => {
    setMessages([]);
    setOperationId(null);
  }, []);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || !deviceId || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    try {
      let res;
      if (!operationId) {
        res = await operationsApi.startChat(deviceId, text, undefined, false);
        setOperationId(res.operation_id);
      } else {
        res = await operationsApi.continueChat(operationId, text);
      }
      setMessages((prev) => [...prev, { role: "assistant", content: res.agent_message }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Erro ao comunicar com o agente. Tente novamente." },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, deviceId, loading, operationId]);

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* ── Botão flutuante ────────────────────────────────────────────────── */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          title={agentLabel}
          className="fixed bottom-6 right-6 z-50 w-14 h-14 bg-brand-600 hover:bg-brand-700 text-white rounded-full shadow-xl flex items-center justify-center transition-transform hover:scale-105"
        >
          <Bot size={26} />
        </button>
      )}

      {/* ── Drawer lateral ────────────────────────────────────────────────── */}
      {isOpen && (
        <div className="fixed right-0 top-0 h-full w-96 bg-white shadow-2xl z-50 flex flex-col border-l border-gray-200">

          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-gray-900 text-white shrink-0">
            <div className="flex items-center gap-2 min-w-0">
              <Bot size={18} className="shrink-0 text-brand-400" />
              <div className="min-w-0">
                <p className="text-sm font-semibold leading-tight">{agentLabel}</p>
                <p className="text-xs text-gray-400 truncate">Contexto: {contextLabel}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0 ml-2">
              <Link
                to={agentPath}
                title="Abrir em tela cheia"
                className="text-gray-400 hover:text-white transition-colors"
              >
                <Maximize2 size={15} />
              </Link>
              <button
                onClick={() => setIsOpen(false)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Seletor de dispositivo */}
          <div className="px-4 py-2 border-b border-gray-100 bg-gray-50 shrink-0">
            <div className="relative">
              <select
                value={deviceId}
                onChange={(e) => {
                  setDeviceId(e.target.value);
                  resetConversation();
                }}
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-1.5 pr-8 bg-white appearance-none focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="">Selecione um dispositivo…</option>
                {devices.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} — {d.vendor}
                  </option>
                ))}
              </select>
              <ChevronDown size={13} className="absolute right-2.5 top-2.5 text-gray-400 pointer-events-none" />
            </div>
          </div>

          {/* Mensagens */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {messages.length === 0 && (
              <div className="text-center text-gray-400 text-sm mt-10 select-none">
                <Bot size={36} className="mx-auto mb-2 opacity-20" />
                <p className="font-medium">Nenhuma mensagem ainda.</p>
                <p className="text-xs mt-1 text-gray-300">
                  Selecione um dispositivo e faça uma pergunta.
                </p>
                <p className="text-xs text-gray-300 mt-0.5">
                  {agentPlaceholderExample}
                </p>
              </div>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[88%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap break-words ${
                    msg.role === "user"
                      ? "bg-brand-600 text-white"
                      : "bg-gray-100 text-gray-800"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-xl px-3 py-2">
                  <Loader2 size={16} className="animate-spin text-gray-500" />
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
                placeholder={
                  deviceId
                    ? "Pergunte ao agente… (Enter para enviar)"
                    : "Selecione um dispositivo primeiro"
                }
                disabled={!deviceId || loading}
                rows={2}
                className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-gray-50 disabled:text-gray-400"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || !deviceId || loading}
                className="self-end w-9 h-9 bg-brand-600 hover:bg-brand-700 text-white rounded-lg flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
              >
                <Send size={15} />
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-1.5 text-center">
              <Link to={agentPath} className="hover:text-brand-600 transition-colors">
                Abrir {agentLabel.toLowerCase()} completo →
              </Link>
            </p>
          </div>
        </div>
      )}
    </>
  );
}
