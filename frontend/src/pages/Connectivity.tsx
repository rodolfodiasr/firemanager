import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Info,
  Loader2,
  Network,
  Play,
  RefreshCw,
  Shield,
  Trash2,
  XCircle,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { connectivityApi } from "../api/connectivity";
import { devicesApi } from "../api/devices";
import type {
  ConnectivityAnalysisRead,
  ConnectivityAnalysisSummary,
  ConnectivityAnomalySeverity,
  ConnectivityStatus,
  SdwanService,
} from "../types/connectivity";
import type { Device } from "../types/device";

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<ConnectivityStatus, string> = {
  pending:   "Aguardando",
  running:   "Analisando",
  completed: "Concluído",
  failed:    "Falhou",
};

const STATUS_STYLE: Record<ConnectivityStatus, string> = {
  pending:   "bg-gray-100 text-gray-600",
  running:   "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed:    "bg-red-100 text-red-700",
};

const SEVERITY_STYLE: Record<string, string> = {
  high:   "bg-red-100 text-red-700 border border-red-200",
  medium: "bg-amber-100 text-amber-700 border border-amber-200",
  low:    "bg-blue-100 text-blue-700 border border-blue-200",
};

const SEVERITY_LABEL: Record<string, string> = {
  high: "Alta", medium: "Média", low: "Baixa",
};

const ANOMALY_TYPE_LABEL: Record<string, string> = {
  no_default_route:       "Sem Rota Padrão",
  static_dynamic_conflict:"Conflito Estático × Dinâmico",
  redundant_no_failover:  "Rotas Redundantes s/ Failover",
  bgp_not_established:    "Peer BGP Não Estabelecido",
  ospf_not_full:          "Vizinho OSPF Não-FULL",
  cidr_overlap:           "Sobreposição de CIDR",
  multi_protocol_conflict:"Conflito Multi-Protocolo",
  sdwan_routing_conflict: "Conflito SD-WAN × Roteamento",
};

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function isInProgress(status: ConnectivityStatus) {
  return status === "pending" || status === "running";
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: ConnectivityStatus }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLE[status]}`}>
      {status === "running" && <Loader2 size={11} className="animate-spin" />}
      {status === "completed" && <CheckCircle2 size={11} />}
      {status === "failed" && <XCircle size={11} />}
      {STATUS_LABEL[status]}
    </span>
  );
}

// ── Detail modal tabs ─────────────────────────────────────────────────────────

type Tab = "routes" | "anomalies" | "bgp_ospf" | "ai";

function RoutesTab({ analysis }: { analysis: ConnectivityAnalysisRead }) {
  const routes = analysis.routes ?? [];
  if (!routes.length) return <p className="text-sm text-gray-500 py-4">Nenhuma rota coletada.</p>;

  const PROTO_STYLE: Record<string, string> = {
    static: "bg-gray-100 text-gray-700",
    connected: "bg-emerald-100 text-emerald-700",
    ospf: "bg-purple-100 text-purple-700",
    bgp: "bg-blue-100 text-blue-700",
    rip: "bg-yellow-100 text-yellow-700",
    unknown: "bg-gray-100 text-gray-500",
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-gray-500 font-medium">
            <th className="pb-2 pr-4">Destino</th>
            <th className="pb-2 pr-4">Próximo Hop</th>
            <th className="pb-2 pr-4">Interface</th>
            <th className="pb-2 pr-4">Protocolo</th>
            <th className="pb-2">Ativo</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {routes.map((r, i) => (
            <tr key={i} className="hover:bg-gray-50">
              <td className="py-1.5 pr-4 font-mono text-xs">{r.destination}/{r.prefix_len}</td>
              <td className="py-1.5 pr-4 font-mono text-xs">{r.next_hop}</td>
              <td className="py-1.5 pr-4 text-xs text-gray-600">{r.interface ?? "—"}</td>
              <td className="py-1.5 pr-4">
                <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${PROTO_STYLE[r.protocol] ?? "bg-gray-100 text-gray-600"}`}>
                  {r.protocol}
                </span>
              </td>
              <td className="py-1.5">
                {r.active
                  ? <CheckCircle2 size={14} className="text-green-500" />
                  : <XCircle size={14} className="text-gray-400" />}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AnomaliesTab({ analysis }: { analysis: ConnectivityAnalysisRead }) {
  const anomalies = analysis.anomalies ?? [];
  if (!anomalies.length) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-gray-500">
        <CheckCircle2 size={32} className="text-green-400" />
        <p className="text-sm">Nenhuma anomalia detectada.</p>
      </div>
    );
  }

  const order: Record<string, number> = { high: 0, medium: 1, low: 2 };
  const sorted = [...anomalies].sort((a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9));

  return (
    <div className="space-y-3">
      {sorted.map((a, i) => (
        <div key={i} className={`p-3 rounded-lg ${SEVERITY_STYLE[a.severity] ?? "bg-gray-100"}`}>
          <div className="flex items-start gap-2">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-semibold uppercase tracking-wide">
                  {SEVERITY_LABEL[a.severity] ?? a.severity}
                </span>
                <span className="text-xs opacity-70">
                  {ANOMALY_TYPE_LABEL[a.type] ?? a.type}
                </span>
              </div>
              <p className="text-sm">{a.description}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function BgpOspfTab({ analysis }: { analysis: ConnectivityAnalysisRead }) {
  const bgp = analysis.bgp_peers ?? [];
  const ospf = analysis.ospf_neighbors ?? [];
  const sdwan = analysis.sdwan_services ?? [];

  if (!bgp.length && !ospf.length && !sdwan.length) {
    return <p className="text-sm text-gray-500 py-4">BGP, OSPF e SD-WAN não detectados neste dispositivo.</p>;
  }

  return (
    <div className="space-y-6">
      {bgp.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
            <Activity size={14} /> Peers BGP
          </h4>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-gray-500 font-medium">
                <th className="pb-2 pr-4">Peer IP</th>
                <th className="pb-2 pr-4">ASN</th>
                <th className="pb-2 pr-4">Estado</th>
                <th className="pb-2 pr-4">Uptime</th>
                <th className="pb-2">Prefixos Recebidos</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {bgp.map((p, i) => {
                const up = p.state?.toLowerCase() === "established";
                return (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="py-1.5 pr-4 font-mono text-xs">{p.peer_ip}</td>
                    <td className="py-1.5 pr-4 text-xs">{p.asn ?? "—"}</td>
                    <td className="py-1.5 pr-4">
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${up ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                        {p.state}
                      </span>
                    </td>
                    <td className="py-1.5 pr-4 text-xs text-gray-600">{p.uptime ?? "—"}</td>
                    <td className="py-1.5 text-xs">{p.prefixes_received}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {ospf.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
            <Network size={14} /> Vizinhos OSPF
          </h4>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-gray-500 font-medium">
                <th className="pb-2 pr-4">Neighbor ID</th>
                <th className="pb-2 pr-4">Estado</th>
                <th className="pb-2 pr-4">Interface</th>
                <th className="pb-2">Endereço</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {ospf.map((n, i) => {
                const full = n.state?.toLowerCase().includes("full");
                return (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="py-1.5 pr-4 font-mono text-xs">{n.neighbor_id}</td>
                    <td className="py-1.5 pr-4">
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${full ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>
                        {n.state}
                      </span>
                    </td>
                    <td className="py-1.5 pr-4 text-xs text-gray-600">{n.interface ?? "—"}</td>
                    <td className="py-1.5 text-xs text-gray-600">{n.address ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {sdwan.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
            <Shield size={14} /> Políticas SD-WAN
          </h4>
          <div className="space-y-2">
            {sdwan.map((svc: SdwanService, i: number) => (
              <div key={i} className="border border-gray-200 rounded-lg p-3 text-xs">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="font-semibold text-gray-800">{svc.name || `Política ${i + 1}`}</span>
                  {svc.mode && (
                    <span className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 font-medium">
                      {svc.mode}
                    </span>
                  )}
                  <span className={`px-1.5 py-0.5 rounded font-medium ${svc.status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}>
                    {svc.status}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-gray-500 block mb-0.5">Destinos</span>
                    {svc.destinations.length > 0
                      ? svc.destinations.map((d, di) => (
                          <span key={di} className="font-mono block">{d}</span>
                        ))
                      : <span className="text-gray-400">Qualquer</span>
                    }
                  </div>
                  <div>
                    <span className="text-gray-500 block mb-0.5">Interfaces WAN</span>
                    {svc.members.length > 0
                      ? svc.members.map((m, mi) => (
                          <span key={mi} className="font-mono block">{m}</span>
                        ))
                      : <span className="text-gray-400">—</span>
                    }
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function AITab({ analysis }: { analysis: ConnectivityAnalysisRead }) {
  if (!analysis.ai_summary && !analysis.ai_recommendations?.length) {
    return <p className="text-sm text-gray-500 py-4">Análise IA não disponível.</p>;
  }

  return (
    <div className="space-y-4">
      {analysis.ai_summary && (
        <div className="bg-blue-50 border border-blue-100 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Shield size={16} className="text-blue-600" />
            <span className="text-sm font-semibold text-blue-800">Análise Geral</span>
          </div>
          <p className="text-sm text-blue-900 whitespace-pre-line">{analysis.ai_summary}</p>
        </div>
      )}

      {(analysis.ai_recommendations ?? []).length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Recomendações</h4>
          <ol className="space-y-2">
            {analysis.ai_recommendations!.map((rec, i) => (
              <li key={i} className="flex gap-2 text-sm text-gray-700">
                <span className="shrink-0 flex items-center justify-center w-5 h-5 rounded-full bg-brand-100 text-brand-700 text-xs font-bold">
                  {i + 1}
                </span>
                <span>{rec}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

// ── Detail modal ──────────────────────────────────────────────────────────────

function DetailModal({
  summaryId,
  deviceName,
  onClose,
}: {
  summaryId: string;
  deviceName: string;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<Tab>("anomalies");

  const { data: analysis, isLoading } = useQuery({
    queryKey: ["connectivity", summaryId],
    queryFn: () => connectivityApi.get(summaryId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && isInProgress(status as ConnectivityStatus) ? 3000 : false;
    },
  });

  const TABS: { id: Tab; label: string }[] = [
    { id: "anomalies", label: "Anomalias" },
    { id: "routes",    label: "Rotas" },
    { id: "bgp_ospf",  label: "BGP / OSPF / SD-WAN" },
    { id: "ai",        label: "Análise IA" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            <Network size={20} className="text-brand-600" />
            <div>
              <h2 className="text-base font-semibold text-gray-900">{deviceName}</h2>
              {analysis && (
                <div className="flex items-center gap-2 mt-0.5">
                  <StatusBadge status={analysis.status as ConnectivityStatus} />
                  {analysis.completed_at && (
                    <span className="text-xs text-gray-500">{fmtDate(analysis.completed_at)}</span>
                  )}
                </div>
              )}
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <XCircle size={20} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b px-6">
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`py-2.5 px-4 text-sm font-medium border-b-2 transition-colors ${
                tab === id
                  ? "border-brand-600 text-brand-700"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {label}
              {id === "anomalies" && analysis?.anomalies?.length
                ? ` (${analysis.anomalies.length})`
                : ""}
              {id === "routes" && analysis?.routes?.length
                ? ` (${analysis.routes.length})`
                : ""}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {isLoading && (
            <div className="flex items-center gap-2 text-gray-500">
              <Loader2 size={16} className="animate-spin" /> Carregando...
            </div>
          )}

          {analysis?.status === "running" && (
            <div className="flex items-center gap-2 mb-4 text-blue-600 text-sm bg-blue-50 rounded-lg px-4 py-2">
              <Loader2 size={14} className="animate-spin" />
              Análise em andamento — atualizando automaticamente...
            </div>
          )}

          {analysis?.status === "failed" && (
            <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-700 text-sm">
              <strong>Erro:</strong> {analysis.error}
            </div>
          )}

          {analysis && analysis.status === "completed" && (
            <>
              {tab === "anomalies" && <AnomaliesTab analysis={analysis} />}
              {tab === "routes"    && <RoutesTab analysis={analysis} />}
              {tab === "bgp_ospf"  && <BgpOspfTab analysis={analysis} />}
              {tab === "ai"        && <AITab analysis={analysis} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function Connectivity() {
  const qc = useQueryClient();
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("");
  const [detailId, setDetailId] = useState<string | null>(null);

  const { data: devices = [] } = useQuery({
    queryKey: ["devices"],
    queryFn: () => devicesApi.list(),
  });

  const { data: analyses = [], isLoading } = useQuery({
    queryKey: ["connectivity"],
    queryFn: connectivityApi.list,
    refetchInterval: (query) => {
      const list = query.state.data ?? [];
      const hasActive = list.some((a) => isInProgress(a.status));
      return hasActive ? 4000 : false;
    },
  });

  const triggerMutation = useMutation({
    mutationFn: connectivityApi.trigger,
    onSuccess: () => {
      toast.success("Análise iniciada");
      qc.invalidateQueries({ queryKey: ["connectivity"] });
    },
    onError: () => toast.error("Falha ao iniciar análise"),
  });

  const deleteMutation = useMutation({
    mutationFn: connectivityApi.remove,
    onSuccess: () => {
      toast.success("Análise excluída");
      qc.invalidateQueries({ queryKey: ["connectivity"] });
    },
    onError: () => toast.error("Falha ao excluir análise"),
  });

  const deviceMap = Object.fromEntries(devices.map((d: Device) => [d.id, d.name]));

  const detailSummary = analyses.find((a) => a.id === detailId);

  return (
    <PageWrapper
      title="Conectividade de Rede"
      subtitle="Análise de tabelas de roteamento, BGP/OSPF e detecção de anomalias"
    >
      {/* Trigger bar */}
      <div className="bg-white border rounded-xl p-4 flex items-center gap-3 mb-6">
        <select
          value={selectedDeviceId}
          onChange={(e) => setSelectedDeviceId(e.target.value)}
          className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">Selecione um dispositivo...</option>
          {devices.map((d: Device) => (
            <option key={d.id} value={d.id}>{d.name} ({d.vendor})</option>
          ))}
        </select>
        <button
          disabled={!selectedDeviceId || triggerMutation.isPending}
          onClick={() => triggerMutation.mutate(selectedDeviceId)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors"
        >
          {triggerMutation.isPending
            ? <Loader2 size={16} className="animate-spin" />
            : <Play size={16} />}
          Analisar Conectividade
        </button>
      </div>

      {/* Analyses table */}
      <div className="bg-white border rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b">
          <h3 className="text-sm font-semibold text-gray-700">Histórico de Análises</h3>
          <button
            onClick={() => qc.invalidateQueries({ queryKey: ["connectivity"] })}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700"
          >
            <RefreshCw size={13} /> Atualizar
          </button>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center gap-2 py-10 text-gray-500">
            <Loader2 size={18} className="animate-spin" /> Carregando...
          </div>
        )}

        {!isLoading && analyses.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-10 text-gray-400">
            <Info size={28} />
            <p className="text-sm">Nenhuma análise ainda. Selecione um dispositivo e clique em Analisar.</p>
          </div>
        )}

        {!isLoading && analyses.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 text-left text-xs text-gray-500 font-medium">
                <th className="px-5 py-2">Dispositivo</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2 text-center">Rotas</th>
                <th className="px-4 py-2 text-center">Anomalias</th>
                <th className="px-4 py-2">Iniciado em</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {analyses.map((a: ConnectivityAnalysisSummary) => (
                <tr
                  key={a.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => setDetailId(a.id)}
                >
                  <td className="px-5 py-3 font-medium text-gray-800">
                    {deviceMap[a.device_id] ?? a.device_id.slice(0, 8)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={a.status} />
                  </td>
                  <td className="px-4 py-3 text-center text-gray-600">{a.route_count}</td>
                  <td className="px-4 py-3 text-center">
                    {a.anomaly_count > 0 ? (
                      <span className="inline-flex items-center gap-1 text-red-600 font-medium">
                        <AlertTriangle size={13} /> {a.anomaly_count}
                      </span>
                    ) : (
                      <span className="text-green-600 text-xs">Nenhuma</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{fmtDate(a.created_at)}</td>
                  <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => setDetailId(a.id)}
                        className="text-gray-400 hover:text-brand-600"
                        title="Ver detalhes"
                      >
                        <ChevronRight size={16} />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm("Excluir esta análise?")) {
                            deleteMutation.mutate(a.id);
                          }
                        }}
                        className="text-gray-300 hover:text-red-500"
                        title="Excluir"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {detailId && detailSummary && (
        <DetailModal
          summaryId={detailId}
          deviceName={deviceMap[detailSummary.device_id] ?? "Dispositivo"}
          onClose={() => setDetailId(null)}
        />
      )}
    </PageWrapper>
  );
}
