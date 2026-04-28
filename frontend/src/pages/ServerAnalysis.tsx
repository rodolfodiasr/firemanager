import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Brain, Send, Loader2, Server as ServerIcon, Database, Shield } from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { serversApi } from "../api/servers";
import { integrationsApi } from "../api/integrations";
import type { AnalyzeResponse } from "../types/server";

// ── Source selector ───────────────────────────────────────────────────────────

interface SourceSelectorProps {
  selectedServers: string[];
  selectedIntegrations: string[];
  onToggleServer: (id: string) => void;
  onToggleIntegration: (id: string) => void;
}

function SourceSelector({
  selectedServers, selectedIntegrations,
  onToggleServer, onToggleIntegration,
}: SourceSelectorProps) {
  const { data: servers = [] } = useQuery({
    queryKey: ["servers"],
    queryFn: serversApi.list,
  });
  const { data: integrations = [] } = useQuery({
    queryKey: ["integrations"],
    queryFn: integrationsApi.list,
  });

  const monitoringIntegrations = integrations.filter(
    (i) => i.type === "zabbix" || i.type === "wazuh"
  );

  return (
    <div className="space-y-4">
      {servers.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
            <ServerIcon size={12} />
            Servidores SSH
          </p>
          <div className="space-y-1">
            {servers.map((s) => (
              <label key={s.id} className="flex items-center gap-2 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={selectedServers.includes(s.id)}
                  onChange={() => onToggleServer(s.id)}
                  className="rounded"
                />
                <span className="text-sm text-gray-700 group-hover:text-gray-900">
                  {s.name}
                  <span className="text-xs text-gray-400 ml-1">{s.host}</span>
                </span>
              </label>
            ))}
          </div>
        </div>
      )}

      {monitoringIntegrations.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
            <Database size={12} />
            Integrações
          </p>
          <div className="space-y-1">
            {monitoringIntegrations.map((i) => {
              const Icon = i.type === "wazuh" ? Shield : Database;
              return (
                <label key={i.id} className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={selectedIntegrations.includes(i.id)}
                    onChange={() => onToggleIntegration(i.id)}
                    className="rounded"
                  />
                  <Icon size={12} className="text-gray-400" />
                  <span className="text-sm text-gray-700 group-hover:text-gray-900">
                    {i.name}
                    <span className="text-xs text-gray-400 ml-1">[{i.type}]</span>
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      )}

      {servers.length === 0 && monitoringIntegrations.length === 0 && (
        <p className="text-xs text-gray-400 italic">
          Nenhuma fonte disponível. Registre servidores ou configure integrações Zabbix/Wazuh.
        </p>
      )}
    </div>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────

interface Message {
  role: "user" | "analyst";
  content: string;
  sources?: string[];
}

function MessageBubble({ msg }: { msg: Message }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] bg-brand-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <div className="h-8 w-8 rounded-full bg-purple-100 flex items-center justify-center shrink-0 mt-0.5">
        <Brain size={14} className="text-purple-600" />
      </div>
      <div className="flex-1">
        <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 text-sm text-gray-800 whitespace-pre-wrap">
          {msg.content}
        </div>
        {msg.sources && msg.sources.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {msg.sources.map((s) => (
              <span key={s} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                {s}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function ServerAnalysis() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedServers, setSelectedServers] = useState<string[]>([]);
  const [selectedIntegrations, setSelectedIntegrations] = useState<string[]>([]);
  const [hostFilter, setHostFilter] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const toggleServer = (id: string) =>
    setSelectedServers((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  const toggleIntegration = (id: string) =>
    setSelectedIntegrations((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  const handleSend = async () => {
    const q = question.trim();
    if (!q || loading) return;
    if (selectedServers.length === 0 && selectedIntegrations.length === 0) {
      alert("Selecione ao menos uma fonte de dados (servidor SSH ou integração Zabbix/Wazuh).");
      return;
    }

    setQuestion("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);

    try {
      const res: AnalyzeResponse = await serversApi.analyze({
        question: q,
        server_ids: selectedServers,
        integration_ids: selectedIntegrations,
        host_filter: hostFilter || undefined,
      });
      setMessages((prev) => [...prev, {
        role: "analyst",
        content: res.answer,
        sources: res.sources_used,
      }]);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setMessages((prev) => [...prev, {
        role: "analyst",
        content: `Erro ao consultar o analista: ${detail ?? "tente novamente"}`,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const noSources = selectedServers.length === 0 && selectedIntegrations.length === 0;

  return (
    <PageWrapper title="Analista N3">
      <div className="flex gap-6 h-[calc(100vh-140px)]">
        {/* Sidebar — fontes */}
        <div className="w-64 shrink-0 flex flex-col gap-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4 flex-1 overflow-y-auto">
            <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <Database size={14} className="text-brand-500" />
              Fontes de dados
            </h3>
            <SourceSelector
              selectedServers={selectedServers}
              selectedIntegrations={selectedIntegrations}
              onToggleServer={toggleServer}
              onToggleIntegration={toggleIntegration}
            />
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Filtrar por host (opcional)
            </label>
            <input
              value={hostFilter}
              onChange={(e) => setHostFilter(e.target.value)}
              placeholder="ex: web-01"
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              Filtra hosts no Zabbix/Wazuh pelo nome.
            </p>
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 flex flex-col bg-white border border-gray-200 rounded-xl overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-8">
                <div className="h-12 w-12 rounded-full bg-purple-100 flex items-center justify-center mb-3">
                  <Brain size={22} className="text-purple-600" />
                </div>
                <p className="font-medium text-gray-700">Analista N3 de Infraestrutura</p>
                <p className="text-sm text-gray-400 mt-1 max-w-sm">
                  Selecione as fontes à esquerda e faça perguntas sobre o estado dos seus servidores.
                </p>
                <div className="mt-4 text-xs text-gray-400 space-y-1">
                  <p>Exemplos de perguntas:</p>
                  <p className="text-brand-500">• Qual servidor está com mais problemas agora?</p>
                  <p className="text-brand-500">• Tem alguma vulnerabilidade crítica aberta?</p>
                  <p className="text-brand-500">• O disco do web-01 está quase cheio?</p>
                  <p className="text-brand-500">• Há serviços com falha nos últimos 30 min?</p>
                </div>
              </div>
            ) : (
              messages.map((m, i) => <MessageBubble key={i} msg={m} />)
            )}
            {loading && (
              <div className="flex gap-3">
                <div className="h-8 w-8 rounded-full bg-purple-100 flex items-center justify-center shrink-0">
                  <Brain size={14} className="text-purple-600" />
                </div>
                <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2">
                  <Loader2 size={14} className="animate-spin text-purple-500" />
                  <span className="text-sm text-gray-400">Coletando dados e analisando...</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t border-gray-200 p-4">
            {noSources && (
              <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3">
                Selecione ao menos uma fonte de dados no painel à esquerda.
              </p>
            )}
            <div className="flex gap-2">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }}}
                placeholder="Pergunte sobre seus servidores..."
                disabled={loading || noSources}
                className="flex-1 border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-gray-50 disabled:text-gray-400"
              />
              <button
                onClick={handleSend}
                disabled={loading || !question.trim() || noSources}
                className="h-10 w-10 bg-brand-600 text-white rounded-xl flex items-center justify-center hover:bg-brand-700 disabled:opacity-50 transition-colors"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </PageWrapper>
  );
}
