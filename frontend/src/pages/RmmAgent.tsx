import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import {
  Monitor, Search, Wifi, WifiOff, Loader2, Activity, Sparkles,
  Terminal, History, Play, CheckCircle2, XCircle, Clock, ChevronDown, ChevronUp, MessageSquare,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { InvestigationPanel } from "../components/investigation/InvestigationPanel";
import { rmmApi, type RmmAgent as RmmAgentType, type RmmScriptRun } from "../api/rmm";

const STATUS_COLORS: Record<string, string> = {
  online:  "text-green-600 bg-green-50",
  offline: "text-red-500  bg-red-50",
  unknown: "text-gray-400  bg-gray-50",
};

function AgentStatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] ?? STATUS_COLORS.unknown;
  const Icon = status === "online" ? Wifi : status === "offline" ? WifiOff : Activity;
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full ${cls}`}>
      <Icon size={9} />
      {status}
    </span>
  );
}

// ── Operate Panel ─────────────────────────────────────────────────────────────

function OperatePanel({ integrationId, agent }: { integrationId: string; agent: RmmAgentType }) {
  const qc = useQueryClient();
  const [shell, setShell] = useState<"powershell" | "cmd" | "bash">("powershell");
  const [body, setBody] = useState("");
  const [result, setResult] = useState<RmmScriptRun | null>(null);

  const runMut = useMutation({
    mutationFn: () => rmmApi.run(integrationId, agent.external_id, {
      run_type: "command", shell, body, timeout: 60,
    }),
    onSuccess: (data) => {
      setResult(data);
      qc.invalidateQueries({ queryKey: ["rmm-script-runs", integrationId] });
    },
  });

  const STATUS_ICON: Record<string, React.ReactNode> = {
    success: <CheckCircle2 size={13} className="text-green-500" />,
    error:   <XCircle size={13} className="text-red-500" />,
    running: <Loader2 size={13} className="animate-spin text-blue-500" />,
    pending: <Clock size={13} className="text-gray-400" />,
  };

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="flex items-center gap-2">
        <Terminal size={14} className="text-brand-500" />
        <p className="text-sm font-semibold text-gray-800">Executar comando em: <span className="text-brand-700">{agent.hostname}</span></p>
      </div>

      <div className="flex gap-2 items-center">
        <label className="text-xs font-medium text-gray-500 shrink-0">Shell:</label>
        {(["powershell", "cmd", "bash"] as const).map((s) => (
          <button key={s} onClick={() => setShell(s)}
            className={`text-xs px-2.5 py-1 rounded-lg border transition-colors font-mono ${
              shell === s ? "bg-brand-600 text-white border-brand-600" : "border-gray-200 text-gray-500 hover:border-gray-300"
            }`}
          >{s}</button>
        ))}
      </div>

      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={6}
        placeholder={
          shell === "powershell"
            ? "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10"
            : shell === "cmd"
            ? "tasklist /fi \"status eq running\""
            : "top -bn1 | head -20"
        }
        className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
      />

      <div className="flex items-center gap-3">
        <button
          onClick={() => { setResult(null); runMut.mutate(); }}
          disabled={!body.trim() || runMut.isPending}
          className="flex items-center gap-1.5 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50 transition-colors"
        >
          {runMut.isPending ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
          {runMut.isPending ? "Executando..." : "Executar"}
        </button>
        {result && (
          <span className="flex items-center gap-1 text-xs text-gray-500">
            {STATUS_ICON[result.status]}
            Exit code: <span className={`font-mono font-semibold ${result.exit_code === 0 ? "text-green-600" : "text-red-600"}`}>{result.exit_code ?? "—"}</span>
          </span>
        )}
      </div>

      {result?.output && (
        <div className="flex-1 bg-gray-900 rounded-xl p-4 overflow-auto">
          <pre className="text-xs text-gray-100 font-mono whitespace-pre-wrap leading-relaxed">{result.output}</pre>
        </div>
      )}

      {runMut.isError && (
        <p className="text-xs text-red-600">
          {(runMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao executar comando."}
        </p>
      )}
    </div>
  );
}

// ── History Panel ─────────────────────────────────────────────────────────────

function HistoryPanel({ integrationId, agentExternalId }: { integrationId: string; agentExternalId: string }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data: runs = [], isLoading } = useQuery({
    queryKey: ["rmm-script-runs", integrationId, agentExternalId],
    queryFn: () => rmmApi.scriptRuns(integrationId, agentExternalId),
    refetchInterval: 5000,
  });

  const STATUS_CFG: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
    success: { label: "Sucesso",    icon: <CheckCircle2 size={12} />, color: "text-green-600 bg-green-50" },
    error:   { label: "Erro",       icon: <XCircle size={12} />,      color: "text-red-600 bg-red-50"     },
    running: { label: "Executando", icon: <Loader2 size={12} className="animate-spin" />, color: "text-blue-600 bg-blue-50" },
    pending: { label: "Aguardando", icon: <Clock size={12} />,        color: "text-gray-500 bg-gray-50"   },
  };

  if (isLoading) return (
    <div className="flex items-center gap-2 text-xs text-gray-400 py-4">
      <Loader2 size={12} className="animate-spin" /> Carregando histórico...
    </div>
  );

  if (runs.length === 0) return (
    <div className="text-center py-8 text-gray-400">
      <Terminal size={28} className="mx-auto mb-2 opacity-20" />
      <p className="text-xs">Nenhum comando executado nesta estação ainda.</p>
    </div>
  );

  return (
    <div className="space-y-2">
      {runs.map((run) => {
        const cfg = STATUS_CFG[run.status] ?? STATUS_CFG.pending;
        const isOpen = expanded === run.id;
        return (
          <div key={run.id} className="border border-gray-100 rounded-xl overflow-hidden">
            <button
              onClick={() => setExpanded(isOpen ? null : run.id)}
              className="w-full flex items-start gap-3 p-3 hover:bg-gray-50 text-left transition-colors"
            >
              <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full shrink-0 mt-0.5 ${cfg.color}`}>
                {cfg.icon}{cfg.label}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-mono text-gray-700 truncate">{run.body}</p>
                <p className="text-[11px] text-gray-400 mt-0.5">
                  {new Date(run.started_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
                  {run.exit_code !== null && ` · exit ${run.exit_code}`}
                  {" · "}<span className="font-mono">{run.shell}</span>
                </p>
              </div>
              {isOpen ? <ChevronUp size={13} className="text-gray-400 shrink-0" /> : <ChevronDown size={13} className="text-gray-400 shrink-0" />}
            </button>
            {isOpen && run.output && (
              <div className="bg-gray-900 px-4 py-3 border-t border-gray-800">
                <pre className="text-xs text-gray-100 font-mono whitespace-pre-wrap leading-relaxed max-h-48 overflow-auto">{run.output}</pre>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function RmmAgent() {
  const location = useLocation();
  const handoffState = location.state as { context?: string; suggested_query?: string } | null;
  const [selectedIntegrationId, setSelectedIntegrationId] = useState<string>("");
  const [selectedAgent, setSelectedAgent] = useState<RmmAgentType | null>(null);
  const [mode, setMode] = useState<"operate" | "history" | "investigate">("investigate");

  const { data: integrations = [], isLoading: loadingIntegrations } = useQuery({
    queryKey: ["rmm"],
    queryFn: rmmApi.list,
  });

  const { data: agents = [], isLoading: loadingAgents } = useQuery({
    queryKey: ["rmm-agents", selectedIntegrationId],
    queryFn: () => rmmApi.agents(selectedIntegrationId),
    enabled: !!selectedIntegrationId,
  });

  const selectedIntegration = integrations.find((i) => i.id === selectedIntegrationId);

  const handleIntegrationChange = (id: string) => {
    setSelectedIntegrationId(id);
    setSelectedAgent(null);
  };

  const targetLabel = selectedAgent
    ? `${selectedAgent.hostname}${selectedIntegration ? ` (${selectedIntegration.name})` : ""}`
    : undefined;

  return (
    <PageWrapper title="Agente · Estações">
      {handoffState?.context && (
        <div className="mb-3 flex items-start gap-2 bg-brand-50 border border-brand-200 rounded-xl px-4 py-2.5">
          <Sparkles size={13} className="text-brand-500 shrink-0 mt-0.5" />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-brand-700">Contexto importado do Assistente IA</p>
            <p className="text-xs text-brand-600 truncate">{handoffState.context.slice(0, 120)}…</p>
          </div>
        </div>
      )}
      <div className="h-[calc(100vh-7rem)] flex gap-4">
        {/* ── Left panel — integration + agent selector ── */}
        <div className="w-64 bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
            <h3 className="text-sm font-semibold text-gray-700">Selecionar Estação</h3>
          </div>

          <div className="flex-1 flex flex-col gap-3 p-4 overflow-y-auto">
            {/* Integration dropdown */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                Integração RMM
              </label>
              {loadingIntegrations ? (
                <div className="flex items-center gap-1.5 text-xs text-gray-400">
                  <Loader2 size={12} className="animate-spin" />
                  Carregando...
                </div>
              ) : integrations.length === 0 ? (
                <p className="text-xs text-gray-400">
                  Nenhuma integração RMM cadastrada.{" "}
                  <a href="/rmm" className="text-brand-600 hover:underline">
                    Configurar
                  </a>
                </p>
              ) : (
                <select
                  value={selectedIntegrationId}
                  onChange={(e) => handleIntegrationChange(e.target.value)}
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option value="">Selecione...</option>
                  {integrations.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Agent list */}
            {selectedIntegrationId && (
              <div className="flex-1 flex flex-col gap-1.5 min-h-0">
                <label className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  Estação / Servidor
                  {agents.length > 0 && (
                    <span className="ml-1.5 normal-case font-normal text-gray-400">
                      ({agents.length})
                    </span>
                  )}
                </label>

                {loadingAgents ? (
                  <div className="flex items-center gap-1.5 text-xs text-gray-400">
                    <Loader2 size={12} className="animate-spin" />
                    Carregando agentes...
                  </div>
                ) : agents.length === 0 ? (
                  <p className="text-xs text-gray-400">
                    Nenhum agente encontrado. Sincronize a integração em{" "}
                    <a href="/rmm" className="text-brand-600 hover:underline">
                      RMM
                    </a>
                    .
                  </p>
                ) : (
                  <div className="flex-1 overflow-y-auto space-y-1">
                    {agents.map((agent) => {
                      const isSelected = selectedAgent?.id === agent.id;
                      return (
                        <button
                          key={agent.id}
                          onClick={() => setSelectedAgent(agent)}
                          className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors ${
                            isSelected
                              ? "bg-brand-600 text-white"
                              : "hover:bg-gray-50 text-gray-700 border border-transparent hover:border-gray-200"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-1 mb-0.5">
                            <p className="text-sm font-medium truncate">{agent.hostname}</p>
                            {!isSelected && <AgentStatusBadge status={agent.status} />}
                          </div>
                          <p className={`text-xs truncate ${isSelected ? "text-blue-200" : "text-gray-400"}`}>
                            {agent.os_name ?? "OS desconhecido"}
                          </p>
                          {agent.ip_address && (
                            <p className={`text-[11px] font-mono ${isSelected ? "text-blue-200" : "text-gray-300"}`}>
                              {agent.ip_address}
                            </p>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ── Right panel — mode switcher + content ── */}
        <div className="flex-1 flex flex-col gap-3 min-h-0">
          {/* Mode buttons */}
          <div className="flex items-center gap-2">
            {([
              ["operate",     "Operar",     <MessageSquare size={12} />],
              ["history",     "Histórico",  <History size={12} />],
              ["investigate", "Investigar", <Search size={12} />],
            ] as const).map(([id, label, icon]) => (
              <button
                key={id}
                onClick={() => setMode(id)}
                disabled={!selectedAgent}
                className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                  mode === id
                    ? id === "operate"     ? "bg-brand-50 border-brand-300 text-brand-700 font-medium"
                    : id === "history"     ? "bg-amber-50 border-amber-300 text-amber-700 font-medium"
                    :                        "bg-violet-50 border-violet-300 text-violet-700 font-medium"
                    : "border-gray-200 text-gray-500 hover:border-gray-300"
                }`}
              >
                {icon}{label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="flex-1 bg-white rounded-xl border border-gray-200 p-5 overflow-y-auto min-h-0">
            {!selectedAgent ? (
              <div className="flex flex-col items-center justify-center h-full gap-4 text-gray-400">
                <div className="w-16 h-16 rounded-2xl bg-gray-50 flex items-center justify-center">
                  <Monitor size={32} className="opacity-30" />
                </div>
                <div className="text-center space-y-1">
                  <p className="text-sm font-medium text-gray-500">Selecione uma estação</p>
                  <p className="text-xs text-gray-400">
                    {integrations.length === 0
                      ? "Configure uma integração RMM para começar."
                      : selectedIntegrationId
                      ? "Escolha um agente na lista ao lado para iniciar."
                      : "Selecione uma integração RMM e depois uma estação."}
                  </p>
                </div>
                {integrations.length === 0 && (
                  <a href="/rmm"
                    className="flex items-center gap-1.5 text-xs px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 font-medium"
                  >
                    <Search size={12} />
                    Configurar RMM
                  </a>
                )}
              </div>
            ) : mode === "operate" ? (
              <OperatePanel integrationId={selectedIntegrationId} agent={selectedAgent} />
            ) : mode === "history" ? (
              <HistoryPanel integrationId={selectedIntegrationId} agentExternalId={selectedAgent.external_id} />
            ) : (
              <InvestigationPanel
                agentType="rmm"
                target={{
                  rmm_integration_id: selectedIntegrationId,
                  rmm_agent_external_id: selectedAgent.external_id,
                }}
                targetLabel={targetLabel}
              />
            )}
          </div>
        </div>
      </div>
    </PageWrapper>
  );
}
