import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Brain, Send, Loader2, Database, Shield, History,
  FileDown, Trash2, ChevronRight, Server as ServerIcon,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { serversApi } from "../api/servers";
import { integrationsApi } from "../api/integrations";
import type { AnalysisSession } from "../types/server";

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
  const { data: servers = [] } = useQuery({ queryKey: ["servers"], queryFn: serversApi.list });
  const { data: integrations = [] } = useQuery({ queryKey: ["integrations"], queryFn: integrationsApi.list });
  const monitoringIntegrations = integrations.filter((i) => i.type === "zabbix" || i.type === "wazuh");

  return (
    <div className="space-y-4">
      {servers.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
            <ServerIcon size={11} /> Servidores SSH
          </p>
          <div className="space-y-1.5">
            {servers.map((s) => (
              <label key={s.id} className="flex items-center gap-2 cursor-pointer group">
                <input type="checkbox" checked={selectedServers.includes(s.id)}
                  onChange={() => onToggleServer(s.id)} className="rounded" />
                <span className="text-sm text-gray-700 group-hover:text-gray-900 truncate">
                  {s.name}
                </span>
              </label>
            ))}
          </div>
        </div>
      )}

      {monitoringIntegrations.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
            <Database size={11} /> Integrações
          </p>
          <div className="space-y-1.5">
            {monitoringIntegrations.map((i) => {
              const Icon = i.type === "wazuh" ? Shield : Database;
              return (
                <label key={i.id} className="flex items-center gap-2 cursor-pointer group">
                  <input type="checkbox" checked={selectedIntegrations.includes(i.id)}
                    onChange={() => onToggleIntegration(i.id)} className="rounded" />
                  <Icon size={11} className="text-gray-400 shrink-0" />
                  <span className="text-sm text-gray-700 group-hover:text-gray-900 truncate">
                    {i.name}
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      )}

      {servers.length === 0 && monitoringIntegrations.length === 0 && (
        <p className="text-xs text-gray-400 italic">
          Nenhuma fonte disponível. Registre servidores ou configure Zabbix/Wazuh.
        </p>
      )}
    </div>
  );
}

// ── History panel ─────────────────────────────────────────────────────────────

interface HistoryPanelProps {
  onLoad: (session: AnalysisSession) => void;
}

function HistoryPanel({ onLoad }: HistoryPanelProps) {
  const qc = useQueryClient();
  const { data: sessions = [], isLoading } = useQuery({
    queryKey: ["analysis-sessions"],
    queryFn: () => serversApi.listSessions(),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => serversApi.deleteSession(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["analysis-sessions"] }),
  });

  const handleExport = (session: AnalysisSession) => {
    const url = serversApi.exportSessionPdfUrl(session.id);
    // attach auth token
    const token = localStorage.getItem("access_token") ?? "";
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `analise_${session.created_at.slice(0, 10)}.pdf`;
        a.click();
      });
  };

  if (isLoading) {
    return <p className="text-xs text-gray-400 flex items-center gap-1"><Loader2 size={11} className="animate-spin" /> Carregando...</p>;
  }

  if (sessions.length === 0) {
    return <p className="text-xs text-gray-400 italic">Nenhuma análise salva ainda.</p>;
  }

  return (
    <div className="space-y-1.5">
      {sessions.map((s) => (
        <div key={s.id}
          className="group flex items-start gap-2 p-2 rounded-lg hover:bg-gray-50 cursor-pointer"
        >
          <ChevronRight size={12} className="text-gray-300 mt-1 shrink-0" />
          <div className="flex-1 min-w-0" onClick={() => onLoad(s)}>
            <p className="text-xs text-gray-700 truncate">{s.question}</p>
            <p className="text-xs text-gray-400">
              {new Date(s.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
            </p>
          </div>
          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
            <button onClick={() => handleExport(s)} title="Exportar PDF"
              className="text-gray-400 hover:text-brand-600 transition-colors">
              <FileDown size={13} />
            </button>
            <button
              onClick={() => { if (confirm("Remover análise?")) deleteMut.mutate(s.id); }}
              title="Remover"
              className="text-gray-300 hover:text-red-500 transition-colors"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────

interface Message {
  role: "user" | "analyst";
  content: string;
  sources?: string[];
  sessionId?: string;
}

function MessageBubble({ msg, onExport }: { msg: Message; onExport?: () => void }) {
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
        <div className="flex items-center gap-3 mt-1.5 flex-wrap">
          {msg.sources && msg.sources.length > 0 && msg.sources.map((s) => (
            <span key={s} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{s}</span>
          ))}
          {onExport && (
            <button onClick={onExport}
              className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium ml-auto">
              <FileDown size={12} /> Exportar PDF
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function ServerAnalysis() {
  const qc = useQueryClient();
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedServers, setSelectedServers] = useState<string[]>([]);
  const [selectedIntegrations, setSelectedIntegrations] = useState<string[]>([]);
  const [hostFilter, setHostFilter] = useState("");
  const [leftTab, setLeftTab] = useState<"sources" | "history">("sources");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const toggleServer = (id: string) =>
    setSelectedServers((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  const toggleIntegration = (id: string) =>
    setSelectedIntegrations((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  const loadSession = (session: AnalysisSession) => {
    setMessages([
      { role: "user", content: session.question },
      { role: "analyst", content: session.answer, sources: session.sources_used, sessionId: session.id },
    ]);
    setLeftTab("sources");
  };

  const handleExportPdf = (sessionId: string) => {
    const url = serversApi.exportSessionPdfUrl(sessionId);
    const token = localStorage.getItem("access_token") ?? "";
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `analise.pdf`;
        a.click();
      });
  };

  const handleSend = async () => {
    const q = question.trim();
    if (!q || loading) return;
    if (selectedServers.length === 0 && selectedIntegrations.length === 0) {
      alert("Selecione ao menos uma fonte de dados.");
      return;
    }

    setQuestion("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);

    try {
      const res = await serversApi.analyze({
        question: q,
        server_ids: selectedServers,
        integration_ids: selectedIntegrations,
        host_filter: hostFilter || undefined,
      });
      // Find the session just saved to get its ID
      const sessions = await serversApi.listSessions(1);
      const sessionId = sessions[0]?.id;

      setMessages((prev) => [...prev, {
        role: "analyst",
        content: res.answer,
        sources: res.sources_used,
        sessionId,
      }]);
      qc.invalidateQueries({ queryKey: ["analysis-sessions"] });
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
        {/* Left panel */}
        <div className="w-64 shrink-0 flex flex-col gap-0 bg-white border border-gray-200 rounded-xl overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-gray-200">
            {(["sources", "history"] as const).map((t) => (
              <button key={t} onClick={() => setLeftTab(t)}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors ${
                  leftTab === t
                    ? "border-b-2 border-brand-600 text-brand-600"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {t === "sources"
                  ? <><Database size={12} /> Fontes</>
                  : <><History size={12} /> Histórico</>}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto p-4">
            {leftTab === "sources" ? (
              <div className="space-y-4">
                <SourceSelector
                  selectedServers={selectedServers}
                  selectedIntegrations={selectedIntegrations}
                  onToggleServer={toggleServer}
                  onToggleIntegration={toggleIntegration}
                />
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Filtrar por host
                  </label>
                  <input
                    value={hostFilter}
                    onChange={(e) => setHostFilter(e.target.value)}
                    placeholder="ex: web-01"
                    className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
              </div>
            ) : (
              <HistoryPanel onLoad={loadSession} />
            )}
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 flex flex-col bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-8">
                <div className="h-12 w-12 rounded-full bg-purple-100 flex items-center justify-center mb-3">
                  <Brain size={22} className="text-purple-600" />
                </div>
                <p className="font-medium text-gray-700">Analista N3 de Infraestrutura</p>
                <p className="text-sm text-gray-400 mt-1 max-w-sm">
                  Selecione as fontes e faça perguntas. Cada análise fica salva no histórico e pode ser exportada em PDF.
                </p>
                <div className="mt-5 grid grid-cols-1 gap-2 w-full max-w-sm">
                  {[
                    "Qual servidor tem mais problemas agora?",
                    "Tem vulnerabilidades críticas abertas?",
                    "Como está o uso de disco e memória?",
                    "Monte um passo a passo para atualizar o Zabbix.",
                  ].map((ex) => (
                    <button key={ex} onClick={() => setQuestion(ex)}
                      className="text-left text-xs bg-gray-50 hover:bg-brand-50 border border-gray-200 hover:border-brand-300 text-gray-600 hover:text-brand-700 rounded-lg px-3 py-2 transition-colors">
                      {ex}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m, i) => (
                <MessageBubble
                  key={i}
                  msg={m}
                  onExport={m.role === "analyst" && m.sessionId
                    ? () => handleExportPdf(m.sessionId!)
                    : undefined}
                />
              ))
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
                Selecione ao menos uma fonte no painel à esquerda.
              </p>
            )}
            <div className="flex gap-2">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                placeholder="Pergunte sobre seus servidores..."
                disabled={loading || noSources}
                className="flex-1 border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-gray-50 disabled:text-gray-400"
              />
              <button onClick={handleSend} disabled={loading || !question.trim() || noSources}
                className="h-10 w-10 bg-brand-600 text-white rounded-xl flex items-center justify-center hover:bg-brand-700 disabled:opacity-50 transition-colors">
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </PageWrapper>
  );
}
