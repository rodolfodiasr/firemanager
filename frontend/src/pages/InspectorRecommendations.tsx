import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ShieldAlert, ScanSearch, RefreshCw, Bot, Terminal,
  ChevronDown, ChevronRight, CheckCircle2, AlertTriangle, Info,
  XCircle,
} from "lucide-react";
import { devicesApi } from "../api/devices";
import type { Recommendation } from "../types/recommendation";

interface Props {
  deviceId: string;
  deviceName?: string;
}

const SEVERITY_CONFIG = {
  high: {
    label: "Alta",
    icon: ShieldAlert,
    pill: "bg-red-100 text-red-700 border-red-200",
    border: "border-l-red-500",
    header: "bg-red-50",
    iconColor: "text-red-500",
  },
  medium: {
    label: "Média",
    icon: AlertTriangle,
    pill: "bg-amber-100 text-amber-700 border-amber-200",
    border: "border-l-amber-400",
    header: "bg-amber-50",
    iconColor: "text-amber-500",
  },
  low: {
    label: "Baixa",
    icon: Info,
    pill: "bg-blue-100 text-blue-700 border-blue-200",
    border: "border-l-blue-400",
    header: "bg-blue-50",
    iconColor: "text-blue-400",
  },
};

function SeverityPill({ severity }: { severity: Recommendation["severity"] }) {
  const cfg = SEVERITY_CONFIG[severity];
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold border ${cfg.pill}`}>
      {severity === "high" ? "Alta" : severity === "medium" ? "Média" : "Baixa"}
    </span>
  );
}

function RecommendationCard({
  rec,
  deviceId,
}: {
  rec: Recommendation;
  deviceId: string;
}) {
  const navigate = useNavigate();
  const [showHint, setShowHint] = useState(false);
  const cfg = SEVERITY_CONFIG[rec.severity];
  const Icon = cfg.icon;

  return (
    <div className={`bg-white rounded-xl border border-gray-200 border-l-4 ${cfg.border} overflow-hidden`}>
      {/* Header */}
      <div className={`px-5 py-4 ${cfg.header} flex items-start gap-3`}>
        <Icon size={18} className={`mt-0.5 shrink-0 ${cfg.iconColor}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <SeverityPill severity={rec.severity} />
            <p className="text-sm font-semibold text-gray-800">{rec.title}</p>
          </div>
          <p className="mt-1.5 text-xs text-gray-600 whitespace-pre-line leading-relaxed">
            {rec.description}
          </p>
        </div>
      </div>

      {/* Affected rules */}
      {rec.affected_rules.length > 0 && (
        <div className="px-5 py-3 border-t border-gray-100">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Regras afetadas ({rec.affected_rules.length})
          </p>
          <div className="flex flex-wrap gap-1.5">
            {rec.affected_rules.map((name) => (
              <span
                key={name}
                className="inline-block px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded font-mono"
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="px-5 py-3 border-t border-gray-100 flex flex-wrap items-center gap-3">
        <button
          onClick={() =>
            navigate(
              `/agent?device=${deviceId}&seed=${encodeURIComponent(rec.agent_seed)}`
            )
          }
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
        >
          <Bot size={14} />
          Corrigir via Agente IA
        </button>

        <button
          onClick={() => setShowHint(!showHint)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          <Terminal size={14} />
          Ver como fazer manualmente
          {showHint ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </button>
      </div>

      {/* Manual hint */}
      {showHint && (
        <div className="px-5 pb-4 border-t border-gray-100 bg-gray-50">
          <pre className="mt-3 text-xs bg-gray-900 text-green-300 border border-gray-700 rounded-lg p-4 overflow-auto whitespace-pre-wrap font-mono leading-relaxed">
            {rec.manual_hint}
          </pre>
        </div>
      )}
    </div>
  );
}

export function InspectorRecommendations({ deviceId, deviceName }: Props) {
  const [triggered, setTriggered] = useState(false);

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["recommendations", deviceId],
    queryFn: () => devicesApi.recommendations(deviceId),
    enabled: triggered,
    staleTime: 120_000,
    retry: false,
  });

  const severityCounts = {
    high:   data?.checks.filter((c) => c.severity === "high").length   ?? 0,
    medium: data?.checks.filter((c) => c.severity === "medium").length ?? 0,
    low:    data?.checks.filter((c) => c.severity === "low").length    ?? 0,
  };

  function handleAnalyze() {
    if (!triggered) {
      setTriggered(true);
    } else {
      refetch();
    }
  }

  return (
    <div className="space-y-5">
      {/* Analysis control bar */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <ScanSearch size={18} className="text-brand-600" />
          <div>
            <p className="text-sm font-semibold text-gray-800">Análise de Segurança</p>
            {data ? (
              <p className="text-xs text-gray-400">
                {data.rules_analyzed} regras verificadas
                {!data.security_fetched && (
                  <span className="ml-2 text-amber-500">· status de segurança indisponível via SSH</span>
                )}
              </p>
            ) : (
              <p className="text-xs text-gray-400">
                Clique em "Analisar" para verificar regras, shadow rules, DPI-SSL e mais.
              </p>
            )}
          </div>
        </div>

        <button
          onClick={handleAnalyze}
          disabled={isFetching}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-semibold rounded-lg hover:bg-brand-700 disabled:opacity-60"
        >
          <RefreshCw size={14} className={isFetching ? "animate-spin" : ""} />
          {triggered && data ? "Reanalisar" : "Analisar Agora"}
        </button>
      </div>

      {/* Loading */}
      {isFetching && (
        <div className="py-16 text-center text-gray-400">
          <RefreshCw size={28} className="mx-auto mb-3 animate-spin text-brand-500" />
          <p className="text-sm font-medium">Analisando {deviceName ?? "dispositivo"}...</p>
          <p className="text-xs mt-1 text-gray-400">Buscando regras e status de segurança via SSH</p>
        </div>
      )}

      {/* Error */}
      {isError && !isFetching && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <XCircle size={28} className="mx-auto mb-2 text-red-400" />
          <p className="text-sm font-medium text-red-700">Falha ao executar análise</p>
          <p className="text-xs text-red-500 mt-1">
            {(error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
              "Verifique a conectividade com o dispositivo."}
          </p>
          <button
            onClick={() => refetch()}
            className="mt-4 px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700"
          >
            Tentar novamente
          </button>
        </div>
      )}

      {/* Empty state — before first analysis */}
      {!triggered && (
        <div className="py-20 text-center text-gray-400">
          <ScanSearch size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Clique em "Analisar Agora" para verificar a política do dispositivo.</p>
          <p className="text-xs mt-1 text-gray-300">
            Verifica shadow rules, DPI-SSL, origens amplas, grupos e mais.
          </p>
        </div>
      )}

      {/* Results */}
      {data && !isFetching && (
        <>
          {/* Summary bar */}
          <div className="flex flex-wrap items-center gap-3">
            {data.total === 0 ? (
              <div className="flex items-center gap-2 px-4 py-2 bg-green-50 border border-green-200 rounded-lg">
                <CheckCircle2 size={16} className="text-green-600" />
                <span className="text-sm font-medium text-green-700">
                  Nenhuma recomendação — política aparentemente bem configurada.
                </span>
              </div>
            ) : (
              <>
                <span className="text-xs text-gray-500 font-medium">
                  {data.total} recomendação(ões) encontrada(s):
                </span>
                {severityCounts.high > 0 && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-700 border border-red-200">
                    <ShieldAlert size={12} /> {severityCounts.high} Alta
                  </span>
                )}
                {severityCounts.medium > 0 && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 border border-amber-200">
                    <AlertTriangle size={12} /> {severityCounts.medium} Média
                  </span>
                )}
                {severityCounts.low > 0 && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-700 border border-blue-200">
                    <Info size={12} /> {severityCounts.low} Baixa
                  </span>
                )}
              </>
            )}
          </div>

          {/* Cards */}
          <div className="space-y-4">
            {data.checks.map((rec) => (
              <RecommendationCard key={rec.id} rec={rec} deviceId={deviceId} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
