import { useEffect, useState } from "react";
import {
  Server, Plus, Trash2, RefreshCw, CheckCircle, AlertCircle,
  Wifi, WifiOff, ChevronRight, Loader2, Settings, FlaskConical,
} from "lucide-react";
import toast from "react-hot-toast";
import { rmmApi, type RmmIntegration, type RmmAgent, type RmmType } from "../api/rmm";

const RMM_TYPES: { value: RmmType; label: string; authFields: { key: string; label: string; type?: string }[] }[] = [
  {
    value: "tactical_rmm",
    label: "Tactical RMM",
    authFields: [{ key: "api_key", label: "API Key" }],
  },
  {
    value: "ninja_rmm",
    label: "NinjaRMM (NinjaOne)",
    authFields: [
      { key: "client_id", label: "Client ID" },
      { key: "client_secret", label: "Client Secret", type: "password" },
    ],
  },
  {
    value: "atera",
    label: "Atera",
    authFields: [{ key: "api_key", label: "API Key" }],
  },
  {
    value: "connectwise_automate",
    label: "ConnectWise Automate",
    authFields: [
      { key: "username", label: "Usuário" },
      { key: "password", label: "Senha", type: "password" },
    ],
  },
];

function StatusBadge({ status }: { status: string | null }) {
  if (status === "ok") return <span className="flex items-center gap-1 text-xs text-green-600"><CheckCircle size={11} />OK</span>;
  if (status === "error") return <span className="flex items-center gap-1 text-xs text-red-500"><AlertCircle size={11} />Erro</span>;
  return <span className="text-xs text-gray-400">—</span>;
}

function AgentStatusDot({ status }: { status: string }) {
  return status === "online"
    ? <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
    : <span className="w-2 h-2 rounded-full bg-gray-300 inline-block" />;
}

export default function RmmPage() {
  const [integrations, setIntegrations] = useState<RmmIntegration[]>([]);
  const [selected, setSelected] = useState<RmmIntegration | null>(null);
  const [agents, setAgents] = useState<RmmAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", rmm_type: "tactical_rmm" as RmmType, base_url: "", credentials: {} as Record<string, string> });

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try { setIntegrations(await rmmApi.list()); }
    catch { toast.error("Erro ao carregar integrações RMM."); }
    finally { setLoading(false); }
  };

  const loadAgents = async (integration: RmmIntegration) => {
    setSelected(integration);
    setAgents([]);
    try { setAgents(await rmmApi.agents(integration.id)); }
    catch { toast.error("Erro ao carregar agentes."); }
  };

  const handleSync = async (id: string) => {
    setSyncing(id);
    try {
      const result = await rmmApi.sync(id);
      toast.success(result.message);
      await load();
      if (selected?.id === id) {
        const updated = integrations.find((i) => i.id === id);
        if (updated) await loadAgents(updated);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao sincronizar.";
      toast.error(msg);
    } finally { setSyncing(null); }
  };

  const handleTest = async (id: string) => {
    try {
      const result = await rmmApi.test(id);
      result.ok ? toast.success(result.message) : toast.error(result.message);
    } catch { toast.error("Erro ao testar conexão."); }
  };

  const handleCreate = async () => {
    const typeInfo = RMM_TYPES.find((t) => t.value === form.rmm_type);
    if (!typeInfo) return;
    const missing = typeInfo.authFields.filter((f) => !form.credentials[f.key]);
    if (missing.length > 0) { toast.error(`Preencha: ${missing.map((f) => f.label).join(", ")}`); return; }
    try {
      await rmmApi.create({ name: form.name, rmm_type: form.rmm_type, base_url: form.base_url, credentials: form.credentials });
      toast.success("Integração criada.");
      setShowForm(false);
      setForm({ name: "", rmm_type: "tactical_rmm", base_url: "", credentials: {} });
      await load();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao criar.";
      toast.error(msg);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Remover integração?")) return;
    try {
      await rmmApi.delete(id);
      toast.success("Integração removida.");
      if (selected?.id === id) { setSelected(null); setAgents([]); }
      await load();
    } catch { toast.error("Erro ao remover."); }
  };

  const selectedType = RMM_TYPES.find((t) => t.value === form.rmm_type);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Server size={24} className="text-brand-600" />
            Integrações RMM
          </h1>
          <p className="text-sm text-gray-500 mt-1">Tactical RMM · NinjaRMM · Atera · ConnectWise Automate</p>
        </div>
        <button onClick={() => setShowForm(true)} className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm">
          <Plus size={15} /> Nova Integração
        </button>
      </div>

      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6 shadow-sm">
          <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-2"><Settings size={16} />Nova Integração RMM</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-gray-600">Nome</label>
              <input className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Ex: Clientes - NinjaRMM" />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600">Tipo de RMM</label>
              <select className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm" value={form.rmm_type} onChange={(e) => setForm({ ...form, rmm_type: e.target.value as RmmType, credentials: {} })}>
                {RMM_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-600">URL Base</label>
              <input className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://rmm.seudominio.com" />
            </div>
            {selectedType?.authFields.map((field) => (
              <div key={field.key}>
                <label className="text-xs font-medium text-gray-600">{field.label}</label>
                <input
                  type={field.type || "text"}
                  className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                  value={form.credentials[field.key] || ""}
                  onChange={(e) => setForm({ ...form, credentials: { ...form.credentials, [field.key]: e.target.value } })}
                />
              </div>
            ))}
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={handleCreate} className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700">Criar</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200">Cancelar</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Lista de integrações */}
        <div className="col-span-1 space-y-3">
          {loading && <div className="flex justify-center py-8"><Loader2 size={20} className="animate-spin text-gray-400" /></div>}
          {!loading && integrations.length === 0 && (
            <div className="text-center py-10 text-gray-400">
              <Server size={36} className="mx-auto mb-2 opacity-20" />
              <p className="text-sm">Nenhuma integração configurada.</p>
            </div>
          )}
          {integrations.map((intg) => (
            <div
              key={intg.id}
              onClick={() => loadAgents(intg)}
              className={`border rounded-xl p-4 cursor-pointer transition-all ${selected?.id === intg.id ? "border-brand-500 bg-brand-50" : "border-gray-200 bg-white hover:border-brand-300"}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm text-gray-900 truncate">{intg.name}</p>
                  <p className="text-xs text-gray-500">{RMM_TYPES.find((t) => t.value === intg.rmm_type)?.label}</p>
                </div>
                <ChevronRight size={14} className="text-gray-400 shrink-0 mt-0.5" />
              </div>
              <div className="flex items-center gap-3 mt-2">
                <span className="text-xs text-gray-600"><strong>{intg.agent_count}</strong> agentes</span>
                <StatusBadge status={intg.last_sync_status} />
              </div>
              <div className="flex gap-1 mt-2">
                <button onClick={(e) => { e.stopPropagation(); handleTest(intg.id); }} title="Testar" className="p-1 text-gray-400 hover:text-brand-600 transition-colors">
                  <FlaskConical size={13} />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleSync(intg.id); }}
                  disabled={syncing === intg.id}
                  title="Sincronizar"
                  className="p-1 text-gray-400 hover:text-green-600 transition-colors disabled:opacity-50"
                >
                  {syncing === intg.id ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                </button>
                <button onClick={(e) => { e.stopPropagation(); handleDelete(intg.id); }} title="Remover" className="p-1 text-gray-400 hover:text-red-500 transition-colors ml-auto">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Detalhe de agentes */}
        <div className="col-span-2 bg-white border border-gray-200 rounded-xl p-5">
          {!selected ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-300 py-16">
              <Server size={48} className="mb-3 opacity-20" />
              <p className="text-sm">Selecione uma integração para ver os agentes.</p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-semibold text-gray-800">{selected.name}</h2>
                <span className="text-xs text-gray-500">{agents.length} agente(s)</span>
              </div>
              {agents.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">Nenhum agente sincronizado. Clique em <RefreshCw size={12} className="inline" /> para sincronizar.</p>
              ) : (
                <div className="overflow-auto max-h-[500px]">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-gray-500 border-b border-gray-100">
                        <th className="pb-2">Status</th>
                        <th className="pb-2">Hostname</th>
                        <th className="pb-2">IP</th>
                        <th className="pb-2">SO</th>
                        <th className="pb-2">Patches</th>
                        <th className="pb-2">Alertas</th>
                      </tr>
                    </thead>
                    <tbody>
                      {agents.map((a) => (
                        <tr key={a.id} className="border-b border-gray-50 hover:bg-gray-50">
                          <td className="py-2"><AgentStatusDot status={a.status} /></td>
                          <td className="py-2 font-medium text-gray-800">{a.hostname}</td>
                          <td className="py-2 text-gray-500">{a.ip_address || "—"}</td>
                          <td className="py-2 text-gray-500 max-w-[120px] truncate">{a.os_name || "—"}</td>
                          <td className="py-2">
                            {a.patches_pending != null ? (
                              <span className={`font-medium ${a.patches_pending > 0 ? "text-amber-600" : "text-gray-400"}`}>{a.patches_pending}</span>
                            ) : "—"}
                          </td>
                          <td className="py-2">
                            {a.alerts_count > 0 ? <span className="text-red-500 font-medium">{a.alerts_count}</span> : <span className="text-gray-400">0</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
