import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowLeftRight,
  CheckCircle2,
  ChevronRight,
  FolderOpen,
  Info,
  Loader2,
  Network,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Shield,
  Trash2,
  X,
  XCircle,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { connectivityApi } from "../api/connectivity";
import { devicesApi } from "../api/devices";
import { networkSegmentsApi, type NetworkSegmentRead, type NetworkSegmentDetail } from "../api/networkSegments";
import type {
  ConnectivityAnalysisRead,
  ConnectivityAnalysisSummary,
  ConnectivityAnomalySeverity,
  ConnectivityMode,
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
  no_default_route:        "Sem Rota Padrão",
  static_dynamic_conflict: "Conflito Estático × Dinâmico",
  redundant_no_failover:   "Rotas Redundantes s/ Failover",
  bgp_not_established:     "Peer BGP Não Estabelecido",
  ospf_not_full:           "Vizinho OSPF Não-FULL",
  cidr_overlap:            "Sobreposição de CIDR",
  multi_protocol_conflict: "Conflito Multi-Protocolo",
  sdwan_routing_conflict:  "Conflito SD-WAN × Roteamento",
  missing_return_route:    "Rota de Retorno Ausente",
  asymmetric_routing:      "Roteamento Assimétrico",
  unreachable_subnet:      "Subrede Inalcançável",
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
      {status === "running"   && <Loader2 size={11} className="animate-spin" />}
      {status === "completed" && <CheckCircle2 size={11} />}
      {status === "failed"    && <XCircle size={11} />}
      {STATUS_LABEL[status]}
    </span>
  );
}

function ModeBadge({ mode }: { mode: ConnectivityMode }) {
  if (mode === "pair") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
        <ArrowLeftRight size={10} /> Ponto-a-Ponto
      </span>
    );
  }
  return null;
}

// ── Tab content components ────────────────────────────────────────────────────

const PROTO_STYLE: Record<string, string> = {
  static:    "bg-gray-100 text-gray-700",
  connected: "bg-emerald-100 text-emerald-700",
  ospf:      "bg-purple-100 text-purple-700",
  bgp:       "bg-blue-100 text-blue-700",
  rip:       "bg-yellow-100 text-yellow-700",
  unknown:   "bg-gray-100 text-gray-500",
};

function RoutesTable({ routes, label }: { routes: { destination: string; prefix_len: number; next_hop: string; interface?: string; protocol: string; active: boolean }[]; label?: string }) {
  if (!routes.length) return <p className="text-sm text-gray-500 py-2">Nenhuma rota coletada.</p>;
  return (
    <div>
      {label && <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{label}</h5>}
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
    </div>
  );
}

function RoutesTab({ analysis, deviceName, deviceBName }: { analysis: ConnectivityAnalysisRead; deviceName: string; deviceBName?: string }) {
  const routes   = analysis.routes ?? [];
  const routesB  = analysis.device_b_routes ?? [];
  const isPair   = analysis.mode === "pair";

  if (!routes.length && !routesB.length) {
    return <p className="text-sm text-gray-500 py-4">Nenhuma rota coletada.</p>;
  }

  return (
    <div className="space-y-6">
      <RoutesTable routes={routes} label={isPair ? deviceName : undefined} />
      {isPair && routesB.length > 0 && (
        <>
          <div className="border-t pt-4">
            <RoutesTable routes={routesB} label={deviceBName} />
          </div>
        </>
      )}
    </div>
  );
}

function AnomaliesTab({ analysis, deviceName, deviceBName }: { analysis: ConnectivityAnalysisRead; deviceName: string; deviceBName?: string }) {
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
      {sorted.map((a, i) => {
        const isPairAnomaly = a._scope === "pair";
        return (
          <div key={i} className={`p-3 rounded-lg ${SEVERITY_STYLE[a.severity] ?? "bg-gray-100"}`}>
            <div className="flex items-start gap-2">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span className="text-xs font-semibold uppercase tracking-wide">
                    {SEVERITY_LABEL[a.severity] ?? a.severity}
                  </span>
                  <span className="text-xs opacity-70">
                    {ANOMALY_TYPE_LABEL[a.type] ?? a.type}
                  </span>
                  {isPairAnomaly && (
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
                      <ArrowLeftRight size={9} /> Cruzada
                    </span>
                  )}
                  {a._device && !isPairAnomaly && (
                    <span className="text-xs opacity-60 font-mono">{a._device}</span>
                  )}
                </div>
                <p className="text-sm">{a.description}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function BgpOspfSection({
  bgp, ospf, sdwan, label,
}: {
  bgp: ConnectivityAnalysisRead["bgp_peers"];
  ospf: ConnectivityAnalysisRead["ospf_neighbors"];
  sdwan: ConnectivityAnalysisRead["sdwan_services"];
  label?: string;
}) {
  const bgpList  = bgp   ?? [];
  const ospfList = ospf  ?? [];
  const sdwanList = sdwan ?? [];

  if (!bgpList.length && !ospfList.length && !sdwanList.length) {
    return <p className="text-sm text-gray-500">BGP, OSPF e SD-WAN não detectados.</p>;
  }

  return (
    <div className="space-y-5">
      {label && <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{label}</h5>}

      {bgpList.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5"><Activity size={14} /> Peers BGP</h4>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-gray-500 font-medium">
                <th className="pb-2 pr-4">Peer IP</th><th className="pb-2 pr-4">ASN</th>
                <th className="pb-2 pr-4">Estado</th><th className="pb-2 pr-4">Uptime</th>
                <th className="pb-2">Prefixos</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {bgpList.map((p, i) => {
                const up = p.state?.toLowerCase() === "established";
                return (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="py-1.5 pr-4 font-mono text-xs">{p.peer_ip}</td>
                    <td className="py-1.5 pr-4 text-xs">{p.asn ?? "—"}</td>
                    <td className="py-1.5 pr-4">
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${up ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>{p.state}</span>
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

      {ospfList.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5"><Network size={14} /> Vizinhos OSPF</h4>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-gray-500 font-medium">
                <th className="pb-2 pr-4">Neighbor ID</th><th className="pb-2 pr-4">Estado</th>
                <th className="pb-2 pr-4">Interface</th><th className="pb-2">Endereço</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {ospfList.map((n, i) => {
                const full = n.state?.toLowerCase().includes("full");
                return (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="py-1.5 pr-4 font-mono text-xs">{n.neighbor_id}</td>
                    <td className="py-1.5 pr-4">
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${full ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>{n.state}</span>
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

      {sdwanList.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5"><Shield size={14} /> Políticas SD-WAN</h4>
          <div className="space-y-2">
            {sdwanList.map((svc: SdwanService, i: number) => (
              <div key={i} className="border border-gray-200 rounded-lg p-3 text-xs">
                <div className="flex flex-wrap items-center gap-2 mb-1.5">
                  <span className="font-semibold text-gray-800">{svc.name || `Política ${i + 1}`}</span>
                  {svc.mode && <span className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 font-medium">{svc.mode}</span>}
                  <span className={`px-1.5 py-0.5 rounded font-medium ${svc.status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}>{svc.status}</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-gray-500 block mb-0.5">Destinos</span>
                    {svc.destinations.length > 0
                      ? svc.destinations.map((d, di) => <span key={di} className="font-mono block">{d}</span>)
                      : <span className="text-gray-400">Qualquer</span>}
                  </div>
                  <div>
                    <span className="text-gray-500 block mb-0.5">Interfaces WAN</span>
                    {svc.members.length > 0
                      ? svc.members.map((m, mi) => <span key={mi} className="font-mono block">{m}</span>)
                      : <span className="text-gray-400">—</span>}
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

function BgpOspfTab({ analysis, deviceName, deviceBName }: { analysis: ConnectivityAnalysisRead; deviceName: string; deviceBName?: string }) {
  const isPair = analysis.mode === "pair";
  return (
    <div className="space-y-6">
      <BgpOspfSection
        bgp={analysis.bgp_peers}
        ospf={analysis.ospf_neighbors}
        sdwan={analysis.sdwan_services}
        label={isPair ? deviceName : undefined}
      />
      {isPair && (
        <div className="border-t pt-4">
          <BgpOspfSection
            bgp={analysis.device_b_bgp_peers}
            ospf={analysis.device_b_ospf_neighbors}
            sdwan={analysis.device_b_sdwan_services}
            label={deviceBName}
          />
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
                <span className="shrink-0 flex items-center justify-center w-5 h-5 rounded-full bg-brand-100 text-brand-700 text-xs font-bold">{i + 1}</span>
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

type Tab = "anomalies" | "routes" | "bgp_ospf" | "ai";

function DetailModal({
  summaryId,
  deviceName,
  deviceBName,
  onClose,
}: {
  summaryId: string;
  deviceName: string;
  deviceBName?: string;
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

  const isPair = analysis?.mode === "pair";
  const pairLabel = isPair ? " (A + B)" : "";

  const TABS: { id: Tab; label: string }[] = [
    { id: "anomalies", label: "Anomalias" },
    { id: "routes",    label: `Rotas${pairLabel}` },
    { id: "bgp_ospf",  label: `BGP / OSPF / SD-WAN${pairLabel}` },
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
              <h2 className="text-base font-semibold text-gray-900">
                {isPair ? `${deviceName} ↔ ${deviceBName ?? "Dispositivo B"}` : deviceName}
              </h2>
              {analysis && (
                <div className="flex items-center gap-2 mt-0.5">
                  <StatusBadge status={analysis.status as ConnectivityStatus} />
                  {analysis.mode === "pair" && <ModeBadge mode="pair" />}
                  {analysis.completed_at && (
                    <span className="text-xs text-gray-500">{fmtDate(analysis.completed_at)}</span>
                  )}
                </div>
              )}
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700"><XCircle size={20} /></button>
        </div>

        {/* Tabs */}
        <div className="flex border-b px-6 overflow-x-auto">
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`py-2.5 px-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                tab === id
                  ? "border-brand-600 text-brand-700"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {label}
              {id === "anomalies" && analysis?.anomalies?.length ? ` (${analysis.anomalies.length})` : ""}
              {id === "routes"    && analysis?.routes?.length    ? ` (${analysis.routes.length}${isPair && analysis.device_b_routes?.length ? `+${analysis.device_b_routes.length}` : ""})` : ""}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {isLoading && (
            <div className="flex items-center gap-2 text-gray-500"><Loader2 size={16} className="animate-spin" /> Carregando...</div>
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

          {analysis?.status === "completed" && analysis.error && (
            <div className="mb-4 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-amber-700 text-sm">
              <strong>Atenção:</strong> {analysis.error}
            </div>
          )}

          {analysis && analysis.status === "completed" && (
            <>
              {tab === "anomalies" && (
                <AnomaliesTab analysis={analysis} deviceName={deviceName} deviceBName={deviceBName} />
              )}
              {tab === "routes" && (
                <RoutesTab analysis={analysis} deviceName={deviceName} deviceBName={deviceBName} />
              )}
              {tab === "bgp_ospf" && (
                <BgpOspfTab analysis={analysis} deviceName={deviceName} deviceBName={deviceBName} />
              )}
              {tab === "ai" && <AITab analysis={analysis} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Network Segment Modal ─────────────────────────────────────────────────────

function NetworkSegmentModal({
  initial,
  devices,
  onClose,
}: {
  initial?: NetworkSegmentDetail | null;
  devices: Device[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [cidr, setCidr] = useState(initial?.cidr ?? "");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    new Set(initial?.devices.map((d) => d.id) ?? [])
  );

  const saveMut = useMutation({
    mutationFn: () => {
      const payload = {
        name,
        description: description || undefined,
        cidr: cidr || undefined,
        device_ids: [...selectedIds],
      };
      return initial
        ? networkSegmentsApi.update(initial.id, payload)
        : networkSegmentsApi.create(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["network-segments"] });
      toast.success(initial ? "Segmento atualizado" : "Segmento criado");
      onClose();
    },
    onError: () => toast.error("Erro ao salvar segmento"),
  });

  const toggle = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-900">
            {initial ? "Editar segmento" : "Novo segmento de rede"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
        </div>
        <div className="overflow-y-auto flex-1 p-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Nome *</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex: LAN Matriz"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Descrição</label>
            <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Opcional"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">CIDR (opcional)</label>
            <input value={cidr} onChange={(e) => setCidr(e.target.value)} placeholder="192.168.1.0/24"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-2">
              Dispositivos ({selectedIds.size} selecionados)
            </label>
            <div className="border border-gray-200 rounded-lg max-h-48 overflow-y-auto divide-y divide-gray-50">
              {devices.length === 0 ? (
                <p className="text-xs text-gray-400 p-3">Nenhum dispositivo disponível</p>
              ) : (
                devices.map((d) => (
                  <label key={d.id} className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer">
                    <input type="checkbox" checked={selectedIds.has(d.id)} onChange={() => toggle(d.id)} className="accent-brand-600" />
                    <span className="text-sm text-gray-700 flex-1 truncate">{d.name}</span>
                    <span className="text-xs text-gray-400">{d.vendor}</span>
                  </label>
                ))
              )}
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 p-4 border-t border-gray-100">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-3 py-2">Cancelar</button>
          <button
            onClick={() => saveMut.mutate()}
            disabled={!name.trim() || saveMut.isPending}
            className="flex items-center gap-1.5 text-sm bg-brand-600 text-white px-4 py-2 rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {saveMut.isPending ? <Loader2 size={14} className="animate-spin" /> : null}
            {initial ? "Salvar" : "Criar"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Network Segments Tab ──────────────────────────────────────────────────────

function NetworkSegmentsTab({ devices }: { devices: Device[] }) {
  const qc = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [editSegment, setEditSegment] = useState<NetworkSegmentDetail | null>(null);
  const [analyzing, setAnalyzing] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<Record<string, string>>({});

  const { data: segments = [], isLoading } = useQuery({
    queryKey: ["network-segments"],
    queryFn: networkSegmentsApi.list,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => networkSegmentsApi.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["network-segments"] }); toast.success("Segmento removido"); },
    onError: () => toast.error("Erro ao remover segmento"),
  });

  const analyzeMut = useMutation({
    mutationFn: (id: string) => networkSegmentsApi.analyze(id),
    onSuccess: (data, id) => {
      setAnalysisResult((prev) => ({
        ...prev,
        [id]: `${data.segment_name} — ${data.device_count} dispositivos analisados. ${data.analyses.length} análises iniciadas.`,
      }));
      toast.success("Análise iniciada para o segmento");
    },
    onError: () => toast.error("Erro ao analisar segmento"),
  });

  const openEdit = async (seg: NetworkSegmentRead) => {
    const detail = await networkSegmentsApi.get(seg.id);
    setEditSegment(detail);
    setShowModal(true);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <p className="text-sm text-gray-500">
          Agrupe dispositivos de rede em segmentos para análise de conectividade em lote.
        </p>
        <button
          onClick={() => { setEditSegment(null); setShowModal(true); }}
          className="flex items-center gap-2 bg-brand-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-brand-700 transition-colors"
        >
          <Plus size={16} /> Novo segmento
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-gray-400 py-8">
          <Loader2 size={16} className="animate-spin" /> Carregando...
        </div>
      ) : segments.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Network size={40} className="text-gray-200 mb-3" />
          <p className="text-gray-500 font-medium">Nenhum segmento criado</p>
          <p className="text-sm text-gray-400 mt-1 max-w-sm">
            Crie segmentos de rede para analisar a conectividade de múltiplos dispositivos de uma vez.
          </p>
          <button onClick={() => { setEditSegment(null); setShowModal(true); }}
            className="mt-4 flex items-center gap-2 bg-brand-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-brand-700">
            <Plus size={16} /> Criar primeiro segmento
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {segments.map((seg) => (
            <div key={seg.id} className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-sm transition-shadow">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="bg-brand-50 text-brand-600 p-2 rounded-lg shrink-0"><FolderOpen size={16} /></div>
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-gray-900 truncate">{seg.name}</h3>
                    {seg.description && <p className="text-xs text-gray-400 truncate">{seg.description}</p>}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0 ml-2">
                  <button onClick={() => openEdit(seg)} className="p-1.5 text-gray-400 hover:text-gray-600 rounded" title="Editar"><Pencil size={13} /></button>
                  <button onClick={() => { if (confirm(`Remover segmento "${seg.name}"?`)) deleteMut.mutate(seg.id); }} className="p-1.5 text-gray-400 hover:text-red-500 rounded" title="Remover"><Trash2 size={13} /></button>
                </div>
              </div>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-xs text-gray-500">
                  {seg.device_count} dispositivo{seg.device_count !== 1 ? "s" : ""}
                </span>
                {seg.cidr && (
                  <span className="text-xs font-mono bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                    {seg.cidr}
                  </span>
                )}
              </div>
              {analysisResult[seg.id] && (
                <div className="mb-2 text-xs text-green-700 bg-green-50 rounded-lg p-2">
                  {analysisResult[seg.id]}
                </div>
              )}
              {analyzing === seg.id ? (
                <div className="flex items-center gap-1 text-xs text-brand-600">
                  <Loader2 size={11} className="animate-spin" /> Analisando...
                </div>
              ) : (
                <button
                  onClick={async () => {
                    setAnalyzing(seg.id);
                    await analyzeMut.mutateAsync(seg.id).catch(() => {});
                    setAnalyzing(null);
                  }}
                  className="flex items-center gap-1.5 text-xs text-brand-600 hover:text-brand-700 font-medium"
                >
                  <Play size={12} /> Analisar conectividade do segmento
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <NetworkSegmentModal
          initial={editSegment}
          devices={devices}
          onClose={() => { setShowModal(false); setEditSegment(null); }}
        />
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

type ConnectivityPageTab = "analyses" | "segments";

export function Connectivity() {
  const qc = useQueryClient();
  const [pageTab, setPageTab] = useState<ConnectivityPageTab>("analyses");
  const [mode, setMode] = useState<ConnectivityMode>("single");
  const [deviceAId, setDeviceAId] = useState("");
  const [deviceBId, setDeviceBId] = useState("");
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
      return list.some((a) => isInProgress(a.status)) ? 4000 : false;
    },
  });

  const triggerSingle = useMutation({
    mutationFn: () => connectivityApi.trigger(deviceAId),
    onSuccess: () => { toast.success("Análise iniciada"); qc.invalidateQueries({ queryKey: ["connectivity"] }); },
    onError: () => toast.error("Falha ao iniciar análise"),
  });

  const triggerPair = useMutation({
    mutationFn: () => connectivityApi.triggerPair(deviceAId, deviceBId),
    onSuccess: () => { toast.success("Análise ponto-a-ponto iniciada"); qc.invalidateQueries({ queryKey: ["connectivity"] }); },
    onError: () => toast.error("Falha ao iniciar análise"),
  });

  const deleteMutation = useMutation({
    mutationFn: connectivityApi.remove,
    onSuccess: () => { toast.success("Análise excluída"); qc.invalidateQueries({ queryKey: ["connectivity"] }); },
    onError: () => toast.error("Falha ao excluir análise"),
  });

  const deviceMap = Object.fromEntries(devices.map((d: Device) => [d.id, d]));
  const detailSummary = analyses.find((a) => a.id === detailId);

  const canTrigger = mode === "single"
    ? !!deviceAId
    : !!deviceAId && !!deviceBId && deviceAId !== deviceBId;

  const isPending = triggerSingle.isPending || triggerPair.isPending;

  function handleTrigger() {
    if (mode === "single") triggerSingle.mutate();
    else triggerPair.mutate();
  }

  return (
    <PageWrapper
      title="Conectividade de Rede"
      subtitle="Análise de tabelas de roteamento, BGP/OSPF e detecção de anomalias"
    >
      {/* Page tab switcher */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {(["analyses", "segments"] as ConnectivityPageTab[]).map((t) => (
          <button
            key={t}
            onClick={() => setPageTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
              pageTab === t
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t === "analyses" ? "Análises" : "Segmentos"}
          </button>
        ))}
      </div>

      {pageTab === "segments" ? (
        <NetworkSegmentsTab devices={devices} />
      ) : (
        <>
      {/* Mode toggle + selectors */}
      <div className="bg-white border rounded-xl p-4 mb-6 space-y-3">
        {/* Toggle */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600 font-medium">Modo:</span>
          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
            <button
              onClick={() => { setMode("single"); setDeviceBId(""); }}
              className={`px-3 py-1.5 font-medium transition-colors ${mode === "single" ? "bg-brand-600 text-white" : "text-gray-600 hover:bg-gray-50"}`}
            >
              Individual
            </button>
            <button
              onClick={() => setMode("pair")}
              className={`px-3 py-1.5 font-medium transition-colors flex items-center gap-1.5 ${mode === "pair" ? "bg-purple-600 text-white" : "text-gray-600 hover:bg-gray-50"}`}
            >
              <ArrowLeftRight size={14} /> Ponto-a-Ponto
            </button>
          </div>
        </div>

        {/* Selectors */}
        <div className="flex items-center gap-3">
          <div className="flex-1">
            {mode === "pair" && (
              <label className="block text-xs text-gray-500 mb-1 font-medium">Firewall A (origem)</label>
            )}
            <select
              value={deviceAId}
              onChange={(e) => setDeviceAId(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">{mode === "pair" ? "Selecione o Firewall A..." : "Selecione um dispositivo..."}</option>
              {devices.map((d: Device) => (
                <option key={d.id} value={d.id} disabled={d.id === deviceBId}>
                  {d.name} ({d.vendor})
                </option>
              ))}
            </select>
          </div>

          {mode === "pair" && (
            <>
              <div className="flex items-end pb-1">
                <ArrowLeftRight size={18} className="text-gray-400" />
              </div>
              <div className="flex-1">
                <label className="block text-xs text-gray-500 mb-1 font-medium">Firewall B (destino)</label>
                <select
                  value={deviceBId}
                  onChange={(e) => setDeviceBId(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="">Selecione o Firewall B...</option>
                  {devices.map((d: Device) => (
                    <option key={d.id} value={d.id} disabled={d.id === deviceAId}>
                      {d.name} ({d.vendor})
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}

          <div className={mode === "pair" ? "flex items-end" : ""}>
            <button
              disabled={!canTrigger || isPending}
              onClick={handleTrigger}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 text-white ${
                mode === "pair"
                  ? "bg-purple-600 hover:bg-purple-700"
                  : "bg-brand-600 hover:bg-brand-700"
              }`}
            >
              {isPending ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
              {mode === "pair" ? "Analisar Par" : "Analisar"}
            </button>
          </div>
        </div>

        {mode === "pair" && deviceAId && deviceBId && deviceAId === deviceBId && (
          <p className="text-xs text-red-500">Selecione dispositivos diferentes para a análise ponto-a-ponto.</p>
        )}
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
                <th className="px-5 py-2">Dispositivo(s)</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2 text-center">Rotas</th>
                <th className="px-4 py-2 text-center">Anomalias</th>
                <th className="px-4 py-2">Iniciado em</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {analyses.map((a: ConnectivityAnalysisSummary) => {
                const devA = deviceMap[a.device_id];
                const devB = a.device_b_id ? deviceMap[a.device_b_id] : null;
                const deviceLabel = devA
                  ? (devB ? `${devA.name} ↔ ${devB.name}` : devA.name)
                  : a.device_id.slice(0, 8);
                return (
                  <tr
                    key={a.id}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => setDetailId(a.id)}
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-800">{deviceLabel}</span>
                        {a.mode === "pair" && <ModeBadge mode="pair" />}
                      </div>
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={a.status} /></td>
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
                        <button onClick={() => setDetailId(a.id)} className="text-gray-400 hover:text-brand-600" title="Ver detalhes">
                          <ChevronRight size={16} />
                        </button>
                        <button
                          onClick={() => { if (confirm("Excluir esta análise?")) deleteMutation.mutate(a.id); }}
                          className="text-gray-300 hover:text-red-500"
                          title="Excluir"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {detailId && detailSummary && (
        <DetailModal
          summaryId={detailId}
          deviceName={deviceMap[detailSummary.device_id]?.name ?? "Dispositivo A"}
          deviceBName={detailSummary.device_b_id ? deviceMap[detailSummary.device_b_id]?.name : undefined}
          onClose={() => setDetailId(null)}
        />
      )}
        </>
      )}
    </PageWrapper>
  );
}
