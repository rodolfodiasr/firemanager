import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus, Trash2, Wifi, WifiOff, RefreshCw, Copy, AlertTriangle,
  ShieldAlert, Activity, Loader2, X, ChevronDown,
} from "lucide-react";
import toast from "react-hot-toast";
import { siemApi } from "../api/siem";
import type { SiemConnector, SiemConnectorCreate, SiemAlert } from "../api/siem";

type Tab = "connectors" | "alerts";

const SIEM_TYPES = ["wazuh", "splunk", "sentinel", "log360", "qradar"] as const;

const SIEM_LABELS: Record<string, string> = {
  wazuh: "Wazuh", splunk: "Splunk", sentinel: "Microsoft Sentinel",
  log360: "Log360", qradar: "IBM QRadar",
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  high:     "bg-orange-100 text-orange-700",
  medium:   "bg-yellow-100 text-yellow-700",
  low:      "bg-blue-100 text-blue-700",
  info:     "bg-gray-100 text-gray-600",
};

// ── Connector Modal ───────────────────────────────────────────────────────────
function ConnectorModal({
  connector,
  onClose,
}: {
  connector?: SiemConnector;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState(connector?.name ?? "");
  const [siemType, setSiemType] = useState(connector?.siem_type ?? "wazuh");
  const [baseUrl, setBaseUrl] = useState(connector?.base_url ?? "");
  const [secret, setSecret] = useState("");

  const createMut = useMutation({
    mutationFn: (d: SiemConnectorCreate) => siemApi.createConnector(d),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["siem-connectors"] });
      toast.success("Conector SIEM criado");
      onClose();
    },
    onError: () => toast.error("Erro ao criar conector"),
  });

  const updateMut = useMutation({
    mutationFn: (d: SiemConnectorCreate) => siemApi.updateConnector(connector!.id, d),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["siem-connectors"] });
      toast.success("Conector atualizado");
      onClose();
    },
    onError: () => toast.error("Erro ao atualizar conector"),
  });

  const isLoading = createMut.isPending || updateMut.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: SiemConnectorCreate = {
      name, siem_type: siemType, base_url: baseUrl,
      ...(secret ? { webhook_secret: secret } : {}),
    };
    connector ? updateMut.mutate(payload) : createMut.mutate(payload);
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg">
        <div className="flex items-center justify-between p-5 border-b">
          <h2 className="text-lg font-semibold text-gray-900">
            {connector ? "Editar Conector SIEM" : "Novo Conector SIEM"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
            <input
              value={name} onChange={e => setName(e.target.value)} required
              placeholder="Wazuh Produção"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tipo de SIEM</label>
            <div className="relative">
              <select
                value={siemType} onChange={e => setSiemType(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                {SIEM_TYPES.map(t => (
                  <option key={t} value={t}>{SIEM_LABELS[t]}</option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-3 top-3 text-gray-400 pointer-events-none" />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">URL Base</label>
            <input
              value={baseUrl} onChange={e => setBaseUrl(e.target.value)} required
              placeholder="https://wazuh.empresa.com:55000"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Webhook Secret <span className="text-gray-400 font-normal">(opcional — gerado automaticamente)</span>
            </label>
            <input
              value={secret} onChange={e => setSecret(e.target.value)}
              placeholder="Deixe em branco para gerar automaticamente"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">
              Cancelar
            </button>
            <button
              type="submit" disabled={isLoading}
              className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2"
            >
              {isLoading && <Loader2 size={14} className="animate-spin" />}
              {connector ? "Salvar" : "Criar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Connector Card ────────────────────────────────────────────────────────────
function ConnectorCard({
  connector,
  onEdit,
  webhookBase,
}: {
  connector: SiemConnector;
  onEdit: () => void;
  webhookBase: string;
}) {
  const qc = useQueryClient();
  const deleteMut = useMutation({
    mutationFn: () => siemApi.deleteConnector(connector.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["siem-connectors"] });
      toast.success("Conector desativado");
    },
  });

  const webhookUrl = `${webhookBase}/webhooks/siem/${connector.webhook_secret}`;

  function copyWebhook() {
    navigator.clipboard.writeText(webhookUrl);
    toast.success("URL copiada");
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-gray-900">{connector.name}</span>
            {connector.is_active ? (
              <Wifi size={14} className="text-green-500" />
            ) : (
              <WifiOff size={14} className="text-gray-400" />
            )}
          </div>
          <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-medium">
            {SIEM_LABELS[connector.siem_type] ?? connector.siem_type}
          </span>
        </div>
        <div className="flex gap-1">
          <button onClick={onEdit} className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-gray-100 rounded-lg transition-colors" title="Editar">
            <RefreshCw size={14} />
          </button>
          <button
            onClick={() => { if (confirm("Desativar este conector?")) deleteMut.mutate(); }}
            className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            title="Desativar"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <p className="text-xs text-gray-500 truncate mb-3">{connector.base_url}</p>

      <div className="bg-gray-50 rounded-lg p-2 flex items-center gap-2">
        <code className="flex-1 text-xs text-gray-600 truncate">{webhookUrl}</code>
        <button onClick={copyWebhook} className="shrink-0 text-gray-400 hover:text-brand-600 transition-colors" title="Copiar URL">
          <Copy size={13} />
        </button>
      </div>

      {connector.last_event_at && (
        <p className="text-xs text-gray-400 mt-2">
          Último evento: {new Date(connector.last_event_at).toLocaleString("pt-BR")}
        </p>
      )}
    </div>
  );
}

// ── Alerts Tab ────────────────────────────────────────────────────────────────
function AlertsTab() {
  const [severity, setSeverity] = useState("");
  const [triggeredOnly, setTriggeredOnly] = useState(false);

  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ["siem-alerts", severity, triggeredOnly],
    queryFn: () => siemApi.listAlerts({
      ...(severity ? { severity } : {}),
      ...(triggeredOnly ? { triggered_only: true } : {}),
      limit: 100,
    }),
  });

  return (
    <div>
      {/* Filters */}
      <div className="flex items-center gap-3 mb-5">
        <div className="relative">
          <select
            value={severity} onChange={e => setSeverity(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm appearance-none pr-8 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Todas as severidades</option>
            {["critical", "high", "medium", "low", "info"].map(s => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
          <ChevronDown size={13} className="absolute right-2.5 top-2.5 text-gray-400 pointer-events-none" />
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox" checked={triggeredOnly} onChange={e => setTriggeredOnly(e.target.checked)}
            className="rounded border-gray-300"
          />
          Apenas com playbook disparado
        </label>
        <span className="ml-auto text-sm text-gray-500">{alerts.length} alerta{alerts.length !== 1 ? "s" : ""}</span>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-gray-400" /></div>
      ) : alerts.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <Activity size={32} className="mx-auto mb-2 text-gray-300" />
          <p className="text-sm">Nenhum alerta recebido ainda.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 uppercase border-b">
                <th className="pb-2 font-medium">Severidade</th>
                <th className="pb-2 font-medium">Título</th>
                <th className="pb-2 font-medium">Host Afetado</th>
                <th className="pb-2 font-medium">IP Fonte</th>
                <th className="pb-2 font-medium">Normalizado em</th>
                <th className="pb-2 font-medium">Playbook</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {alerts.map((a: SiemAlert) => (
                <tr key={a.id} className="hover:bg-gray-50">
                  <td className="py-3 pr-4">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${SEVERITY_COLORS[a.severity] ?? "bg-gray-100 text-gray-600"}`}>
                      {a.severity}
                    </span>
                  </td>
                  <td className="py-3 pr-4 max-w-xs truncate text-gray-900 font-medium">{a.title}</td>
                  <td className="py-3 pr-4 text-gray-600 font-mono text-xs">{a.affected_host ?? "—"}</td>
                  <td className="py-3 pr-4 text-gray-600 font-mono text-xs">{a.source_ip ?? "—"}</td>
                  <td className="py-3 pr-4 text-gray-500 whitespace-nowrap">
                    {new Date(a.normalized_at).toLocaleString("pt-BR")}
                  </td>
                  <td className="py-3">
                    {a.playbook_triggered ? (
                      <span className="text-xs text-green-700 bg-green-100 px-2 py-0.5 rounded-full">Disparado</span>
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function SiemPage() {
  const [tab, setTab] = useState<Tab>("connectors");
  const [showModal, setShowModal] = useState(false);
  const [editConnector, setEditConnector] = useState<SiemConnector | undefined>();

  const { data: connectors = [], isLoading } = useQuery({
    queryKey: ["siem-connectors"],
    queryFn: siemApi.listConnectors,
  });

  const webhookBase = window.location.origin;

  const tabClass = (t: Tab) =>
    `px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
      tab === t ? "bg-brand-600 text-white" : "text-gray-600 hover:bg-gray-100"
    }`;

  return (
    <div className="ml-64 p-8 min-h-screen bg-gray-50">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <ShieldAlert size={24} className="text-brand-600" />
            Integrações SIEM
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            Conecte Wazuh, Splunk, Sentinel e outros SIEMs para fechar o loop detecção→resposta.
          </p>
        </div>
        {tab === "connectors" && (
          <button
            onClick={() => { setEditConnector(undefined); setShowModal(true); }}
            className="flex items-center gap-2 bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 transition-colors"
          >
            <Plus size={16} />
            Novo Conector
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button className={tabClass("connectors")} onClick={() => setTab("connectors")}>
          <span className="flex items-center gap-1.5"><Wifi size={14} /> Conectores ({connectors.length})</span>
        </button>
        <button className={tabClass("alerts")} onClick={() => setTab("alerts")}>
          <span className="flex items-center gap-1.5"><AlertTriangle size={14} /> Alertas</span>
        </button>
      </div>

      {/* Content */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        {tab === "connectors" && (
          <>
            {isLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 size={24} className="animate-spin text-gray-400" />
              </div>
            ) : connectors.length === 0 ? (
              <div className="text-center py-16 text-gray-500">
                <ShieldAlert size={40} className="mx-auto mb-3 text-gray-300" />
                <p className="font-medium mb-1">Nenhum conector SIEM configurado</p>
                <p className="text-sm text-gray-400 mb-4">
                  Adicione um conector para receber alertas e automatizar respostas.
                </p>
                <button
                  onClick={() => setShowModal(true)}
                  className="inline-flex items-center gap-2 bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-700"
                >
                  <Plus size={15} /> Adicionar Conector
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {connectors.map((c: SiemConnector) => (
                  <ConnectorCard
                    key={c.id}
                    connector={c}
                    webhookBase={webhookBase}
                    onEdit={() => { setEditConnector(c); setShowModal(true); }}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {tab === "alerts" && <AlertsTab />}
      </div>

      {/* Webhook info banner */}
      {tab === "connectors" && connectors.length > 0 && (
        <div className="mt-4 bg-blue-50 border border-blue-200 rounded-xl p-4 flex gap-3 items-start">
          <Activity size={18} className="text-blue-600 shrink-0 mt-0.5" />
          <div className="text-sm text-blue-800">
            <strong>Como configurar o webhook:</strong>{" "}
            Copie a URL do conector e configure no seu SIEM como destino de alertas.
            Para <strong>Wazuh</strong>: <em>Manager → Integrations</em>.
            Para <strong>Splunk</strong>: <em>Alert Action → Custom Webhook</em>.
            Para <strong>Sentinel</strong>: <em>Logic App com HTTP Trigger</em>.
          </div>
        </div>
      )}

      {showModal && (
        <ConnectorModal
          connector={editConnector}
          onClose={() => { setShowModal(false); setEditConnector(undefined); }}
        />
      )}
    </div>
  );
}
