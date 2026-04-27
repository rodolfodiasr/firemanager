import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ShieldAlert, ScanSearch, RefreshCw, Bot, Terminal,
  ChevronDown, ChevronRight, CheckCircle2, AlertTriangle, Info,
  XCircle, ExternalLink,
} from "lucide-react";
import { devicesApi } from "../api/devices";
import type { Recommendation, RuleRow } from "../types/recommendation";

interface Props {
  deviceId: string;
  deviceName?: string;
  onViewRule: (ruleName: string) => void;
}

const SEVERITY_CONFIG = {
  high: {
    icon: ShieldAlert,
    pill: "bg-red-100 text-red-700 border-red-200",
    border: "border-l-red-500",
    header: "bg-red-50",
    iconColor: "text-red-500",
  },
  medium: {
    icon: AlertTriangle,
    pill: "bg-amber-100 text-amber-700 border-amber-200",
    border: "border-l-amber-400",
    header: "bg-amber-50",
    iconColor: "text-amber-500",
  },
  low: {
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
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${cfg.pill}`}>
      {severity === "high" ? "Alta" : severity === "medium" ? "Média" : "Baixa"}
    </span>
  );
}

function ActionBadge({ action }: { action: string }) {
  const v = action.toLowerCase();
  const cls =
    v === "allow" ? "text-green-700" :
    v === "deny"  ? "text-red-600"   : "text-gray-500";
  return <span className={`text-xs font-semibold uppercase ${cls}`}>{action}</span>;
}

function EnabledBadge({ enabled }: { enabled: boolean }) {
  return enabled ? (
    <span className="inline-flex items-center gap-0.5 text-green-700 text-xs font-medium">
      <CheckCircle2 size={11} /> Ativo
    </span>
  ) : (
    <span className="inline-flex items-center gap-0.5 text-red-500 text-xs font-medium">
      <XCircle size={11} /> Inativo
    </span>
  );
}

function HitCount({ count }: { count: number | null | undefined }) {
  if (count === null || count === undefined)
    return <span className="text-gray-300 text-xs">N/D</span>;
  if (count === 0)
    return <span className="text-gray-400 text-xs">0</span>;
  return <span className="text-amber-600 text-xs font-medium">{count.toLocaleString("pt-BR")}</span>;
}

function AffectedRulesTable({
  rules,
  showHits,
  onViewRule,
}: {
  rules: RuleRow[];
  showHits: boolean;
  onViewRule: (name: string) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200 text-left text-gray-400 uppercase tracking-wide">
            <th className="px-3 py-2 w-10 font-semibold">#</th>
            <th className="px-3 py-2 font-semibold">Nome</th>
            <th className="px-3 py-2 font-semibold whitespace-nowrap">Zona</th>
            <th className="px-3 py-2 font-semibold">Origem</th>
            <th className="px-3 py-2 font-semibold">Destino</th>
            <th className="px-3 py-2 font-semibold">Serviço</th>
            <th className="px-3 py-2 font-semibold">Ação</th>
            <th className="px-3 py-2 font-semibold">Status</th>
            {showHits && <th className="px-3 py-2 font-semibold text-right">Hits</th>}
            <th className="px-3 py-2 w-6" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rules.map((rule) => (
            <tr
              key={rule.rule_id || rule.name}
              className={`transition-colors hover:bg-gray-50 ${!rule.enabled ? "opacity-50" : ""}`}
            >
              <td className="px-3 py-2 text-center">
                {rule.pos != null ? (
                  <span className="font-mono text-gray-400 bg-gray-100 rounded px-1.5 py-0.5 text-xs">
                    #{rule.pos}
                  </span>
                ) : (
                  <span className="text-gray-300">—</span>
                )}
              </td>
              <td className="px-3 py-2">
                <div>
                  <span className="font-medium text-gray-800 truncate max-w-[160px] block">
                    {rule.name}
                  </span>
                  {rule.shadowed_by && (
                    <span className="text-gray-400 text-xs">encoberta por: {rule.shadowed_by}</span>
                  )}
                </div>
              </td>
              <td className="px-3 py-2 whitespace-nowrap text-gray-600">
                {rule.src_zone && rule.dst_zone
                  ? `${rule.src_zone} → ${rule.dst_zone}`
                  : rule.src_zone || rule.dst_zone || "—"}
              </td>
              <td className="px-3 py-2 text-gray-700 truncate max-w-[120px]">{rule.src || "—"}</td>
              <td className="px-3 py-2 text-gray-700 truncate max-w-[120px]">{rule.dst || "—"}</td>
              <td className="px-3 py-2 text-gray-600 truncate max-w-[100px]">{rule.service || "—"}</td>
              <td className="px-3 py-2"><ActionBadge action={rule.action} /></td>
              <td className="px-3 py-2"><EnabledBadge enabled={rule.enabled} /></td>
              {showHits && (
                <td className="px-3 py-2 text-right">
                  <HitCount count={rule.hit_count} />
                </td>
              )}
              <td className="px-3 py-2">
                <button
                  onClick={() => onViewRule(rule.name)}
                  title="Ver no Inspetor"
                  className="text-gray-300 hover:text-brand-600 transition-colors"
                >
                  <ExternalLink size={13} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RecommendationCard({
  rec,
  deviceId,
  onViewRule,
}: {
  rec: Recommendation;
  deviceId: string;
  onViewRule: (name: string) => void;
}) {
  const navigate = useNavigate();
  const [showHint, setShowHint] = useState(false);
  const cfg = SEVERITY_CONFIG[rec.severity];
  const Icon = cfg.icon;
  const showHits = rec.id === "disabled_rules";

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
          <p className="mt-1.5 text-xs text-gray-600 leading-relaxed">{rec.description}</p>
        </div>
      </div>

      {/* Affected rules table */}
      {rec.affected_rules.length > 0 && (
        <div className="px-5 py-3 border-t border-gray-100">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Regras afetadas ({rec.affected_rules.length})
          </p>
          <AffectedRulesTable
            rules={rec.affected_rules}
            showHits={showHits}
            onViewRule={onViewRule}
          />
        </div>
      )}

      {/* Actions */}
      <div className="px-5 py-3 border-t border-gray-100 flex flex-wrap items-center gap-3">
        <button
          onClick={() =>
            navigate(`/agent?device=${deviceId}&seed=${encodeURIComponent(rec.agent_seed)}`)
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

export function InspectorRecommendations({ deviceId, deviceName, onViewRule }: Props) {
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
    if (!triggered) setTriggered(true);
    else refetch();
  }

  return (
    <div className="space-y-5">
      {/* Control bar */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <ScanSearch size={18} className="text-brand-600" />
          <div>
            <p className="text-sm font-semibold text-gray-800">Análise de Segurança</p>
            {data ? (
              <p className="text-xs text-gray-400">
                {data.rules_analyzed} regras verificadas
                {!data.security_fetched && (
                  <span className="ml-2 text-amber-500">· serviços de segurança indisponíveis</span>
                )}
                {!data.stats_fetched && (
                  <span className="ml-2 text-gray-300">· hit counts indisponíveis</span>
                )}
              </p>
            ) : (
              <p className="text-xs text-gray-400">
                Clique em "Analisar" para verificar shadow rules, DPI-SSL, grupos e mais.
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
          <p className="text-xs mt-1 text-gray-400">Buscando regras e status de segurança</p>
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
          <button onClick={() => refetch()} className="mt-4 px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700">
            Tentar novamente
          </button>
        </div>
      )}

      {/* Empty state */}
      {!triggered && (
        <div className="py-20 text-center text-gray-400">
          <ScanSearch size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Clique em "Analisar Agora" para verificar a política do dispositivo.</p>
          <p className="text-xs mt-1 text-gray-300">Verifica shadow rules, DPI-SSL, origens amplas, grupos e mais.</p>
        </div>
      )}

      {/* Results */}
      {data && !isFetching && (
        <>
          {/* Summary */}
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
                <span className="text-xs text-gray-500 font-medium">{data.total} recomendação(ões):</span>
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
              <RecommendationCard
                key={rec.id}
                rec={rec}
                deviceId={deviceId}
                onViewRule={onViewRule}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
