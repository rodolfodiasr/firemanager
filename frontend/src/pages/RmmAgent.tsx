import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { Monitor, Search, Wifi, WifiOff, Loader2, Activity, Sparkles } from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import { InvestigationPanel } from "../components/investigation/InvestigationPanel";
import { rmmApi, type RmmAgent as RmmAgentType } from "../api/rmm";

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

export default function RmmAgent() {
  const location = useLocation();
  const handoffState = location.state as { context?: string; suggested_query?: string } | null;
  const [selectedIntegrationId, setSelectedIntegrationId] = useState<string>("");
  const [selectedAgent, setSelectedAgent] = useState<RmmAgentType | null>(null);

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

        {/* ── Right panel — investigation ── */}
        <div className="flex-1 bg-white rounded-xl border border-gray-200 p-5 overflow-y-auto">
          {selectedAgent ? (
            <InvestigationPanel
              agentType="rmm"
              target={{
                rmm_integration_id: selectedIntegrationId,
                rmm_agent_external_id: selectedAgent.external_id,
              }}
              targetLabel={targetLabel}
            />
          ) : (
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
                    ? "Escolha um agente na lista ao lado para iniciar o diagnóstico."
                    : "Selecione uma integração RMM e depois uma estação."}
                </p>
              </div>
              {integrations.length === 0 && (
                <a
                  href="/rmm"
                  className="flex items-center gap-1.5 text-xs px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 font-medium"
                >
                  <Search size={12} />
                  Configurar RMM
                </a>
              )}
            </div>
          )}
        </div>
      </div>
    </PageWrapper>
  );
}
