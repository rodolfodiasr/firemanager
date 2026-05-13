import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  edgeAgentsApi,
  type EdgeAgent,
  type MarketplacePlugin,
  type RbacCustomRole,
  type TenantPlugin,
} from "../api/edgeAgents";
import {
  Cpu, KeyRound, Store, Shield, Plus, Trash2,
  Wifi, WifiOff, CheckCircle, Download, X,
} from "lucide-react";

type Tab = "agents" | "sso" | "marketplace" | "rbac";

export function EdgeAgentsPage() {
  const [tab, setTab] = useState<Tab>("agents");

  const tabs: { id: Tab; label: string; icon: React.ComponentType<{ size?: number | string }> }[] = [
    { id: "agents", label: "Edge Agents", icon: Cpu },
    { id: "sso", label: "SSO / OIDC", icon: KeyRound },
    { id: "marketplace", label: "Marketplace", icon: Store },
    { id: "rbac", label: "RBAC Granular", icon: Shield },
  ];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Plataforma Avançada</h1>
        <p className="text-gray-400 text-sm mt-1">Edge Agents, SSO, Marketplace de plugins e RBAC granular</p>
      </div>

      <div className="flex gap-2 border-b border-gray-700">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === id
                ? "border-brand-500 text-brand-400"
                : "border-transparent text-gray-400 hover:text-white"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {tab === "agents" && <AgentsTab />}
      {tab === "sso" && <SsoTab />}
      {tab === "marketplace" && <MarketplaceTab />}
      {tab === "rbac" && <RbacTab />}
    </div>
  );
}

// ── Agents Tab ────────────────────────────────────────────────────────────────

function AgentsTab() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [newToken, setNewToken] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", notes: "" });

  const { data: agents = [] } = useQuery({ queryKey: ["edge-agents"], queryFn: edgeAgentsApi.listAgents });

  const createMut = useMutation({
    mutationFn: () => edgeAgentsApi.createAgent(form),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["edge-agents"] });
      setNewToken(data.token);
      setShowForm(false);
      setForm({ name: "", notes: "" });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => edgeAgentsApi.deleteAgent(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["edge-agents"] }),
  });

  return (
    <div className="space-y-4">
      <div className="bg-blue-900/20 border border-blue-700 rounded-lg p-4 text-sm text-blue-300">
        Edge Agents permitem gerenciar dispositivos atrás de CGNAT sem expor portas.
        O agente instala-se no ambiente do cliente e abre conexão WebSocket sainte para o SaaS.
        <code className="block mt-2 bg-gray-900 rounded px-3 py-2 text-green-400 text-xs">
          docker run firemanager/edge-agent --token TOKEN
        </code>
      </div>

      <div className="flex justify-end">
        <button onClick={() => setShowForm(v => !v)} className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
          <Plus size={14} /> Registrar Agent
        </button>
      </div>

      {newToken && (
        <div className="bg-yellow-900/20 border border-yellow-700 rounded-lg p-4 space-y-2">
          <p className="text-yellow-300 text-sm font-medium">Token gerado — salve agora, não será exibido novamente:</p>
          <code className="block bg-gray-900 rounded px-3 py-2 text-green-400 text-xs break-all">{newToken}</code>
          <button onClick={() => setNewToken(null)} className="text-xs text-gray-400 hover:text-white flex items-center gap-1"><X size={12} /> Fechar</button>
        </div>
      )}

      {showForm && (
        <div className="bg-gray-800 rounded-lg p-4 space-y-3 border border-gray-700">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Nome do Agent</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="ex: Filial SP" className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Observações</label>
              <input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="px-3 py-1.5 text-sm text-gray-400 hover:text-white">Cancelar</button>
            <button onClick={() => createMut.mutate()} disabled={!form.name} className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded text-sm disabled:opacity-50">Gerar Token</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {agents.map((a: EdgeAgent) => (
          <div key={a.id} className="bg-gray-800 rounded-lg p-4 flex items-center justify-between border border-gray-700">
            <div className="flex items-center gap-3">
              {a.status === "online" ? <Wifi size={16} className="text-green-400" /> : <WifiOff size={16} className="text-gray-500" />}
              <div>
                <span className="font-medium text-white">{a.name}</span>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={`text-xs px-2 py-0.5 rounded ${a.status === "online" ? "bg-green-900/50 text-green-300" : "bg-gray-700 text-gray-400"}`}>{a.status}</span>
                  {a.version && <span className="text-xs text-gray-500">v{a.version}</span>}
                  {a.ip_address && <span className="text-xs text-gray-500">{a.ip_address}</span>}
                  {a.last_seen && <span className="text-xs text-gray-500">visto {new Date(a.last_seen).toLocaleString("pt-BR")}</span>}
                </div>
              </div>
            </div>
            <button onClick={() => deleteMut.mutate(a.id)} className="p-2 text-gray-500 hover:text-red-400 transition-colors">
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        {agents.length === 0 && <p className="text-gray-500 text-sm text-center py-8">Nenhum edge agent registrado.</p>}
      </div>
    </div>
  );
}

// ── SSO Tab ───────────────────────────────────────────────────────────────────

function SsoTab() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    provider: "azure_ad",
    client_id: "",
    client_secret: "",
    discovery_url: "",
    group_claim: "groups",
    sso_required: false,
  });

  const { data: sso } = useQuery({ queryKey: ["sso-config"], queryFn: edgeAgentsApi.getSsoConfig });

  const saveMut = useMutation({
    mutationFn: () => edgeAgentsApi.upsertSsoConfig(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["sso-config"] }); setEditing(false); },
  });

  const deleteMut = useMutation({
    mutationFn: edgeAgentsApi.deleteSsoConfig,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sso-config"] }),
  });

  const PROVIDERS = [
    { value: "azure_ad", label: "Azure AD / Entra ID", url: "https://login.microsoftonline.com/{tenant}/.well-known/openid-configuration" },
    { value: "okta", label: "Okta", url: "https://{domain}/.well-known/openid-configuration" },
    { value: "google", label: "Google Workspace", url: "https://accounts.google.com/.well-known/openid-configuration" },
    { value: "custom_oidc", label: "OIDC Customizado", url: "" },
  ];

  return (
    <div className="space-y-4 max-w-2xl">
      {!sso && !editing ? (
        <div className="text-center py-12">
          <KeyRound size={40} className="text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400 mb-4">Nenhuma configuração SSO/OIDC configurada.</p>
          <button onClick={() => setEditing(true)} className="bg-brand-600 hover:bg-brand-700 text-white px-6 py-2 rounded-lg text-sm">Configurar SSO</button>
        </div>
      ) : !editing ? (
        <div className="bg-gray-800 rounded-lg p-5 border border-gray-700 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle size={16} className="text-green-400" />
              <span className="font-medium text-white">SSO Configurado</span>
            </div>
            <div className="flex gap-2">
              <button onClick={() => { setForm({ provider: sso!.provider, client_id: sso!.client_id, client_secret: "", discovery_url: sso!.discovery_url, group_claim: sso!.group_claim || "groups", sso_required: sso!.sso_required }); setEditing(true); }} className="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded">Editar</button>
              <button onClick={() => deleteMut.mutate()} className="px-3 py-1.5 text-sm bg-red-800/50 hover:bg-red-700/50 text-red-300 rounded">Remover</button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><span className="text-gray-400">Provider:</span> <span className="text-white">{sso!.provider}</span></div>
            <div><span className="text-gray-400">Client ID:</span> <span className="text-white">{sso!.client_id}</span></div>
            <div className="col-span-2"><span className="text-gray-400">Discovery URL:</span> <span className="text-white text-xs">{sso!.discovery_url}</span></div>
            <div><span className="text-gray-400">Group Claim:</span> <span className="text-white">{sso!.group_claim}</span></div>
            <div><span className="text-gray-400">SSO Obrigatório:</span> <span className={sso!.sso_required ? "text-yellow-300" : "text-gray-400"}>{sso!.sso_required ? "Sim" : "Não"}</span></div>
          </div>
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg p-5 border border-gray-700 space-y-4">
          <h3 className="font-semibold text-white">Configuração SSO / OIDC</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Provider</label>
              <select value={form.provider} onChange={e => { const p = PROVIDERS.find(x => x.value === e.target.value); setForm(f => ({ ...f, provider: e.target.value, discovery_url: p?.url || "" })); }} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm">
                {PROVIDERS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Client ID</label>
              <input value={form.client_id} onChange={e => setForm(f => ({ ...f, client_id: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Client Secret</label>
              <input type="password" value={form.client_secret} onChange={e => setForm(f => ({ ...f, client_secret: e.target.value }))} placeholder="deixe em branco para manter" className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Group Claim</label>
              <input value={form.group_claim} onChange={e => setForm(f => ({ ...f, group_claim: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Discovery URL</label>
            <input value={form.discovery_url} onChange={e => setForm(f => ({ ...f, discovery_url: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.sso_required} onChange={e => setForm(f => ({ ...f, sso_required: e.target.checked }))} className="rounded" />
            <span className="text-sm text-gray-300">SSO obrigatório (bloqueia login local)</span>
          </label>
          <div className="flex justify-end gap-2">
            <button onClick={() => setEditing(false)} className="px-3 py-1.5 text-sm text-gray-400 hover:text-white">Cancelar</button>
            <button onClick={() => saveMut.mutate()} disabled={!form.client_id || !form.discovery_url} className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded text-sm disabled:opacity-50">Salvar</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Marketplace Tab ───────────────────────────────────────────────────────────

function MarketplaceTab() {
  const qc = useQueryClient();

  const { data: plugins = [] } = useQuery({ queryKey: ["marketplace-plugins"], queryFn: edgeAgentsApi.listMarketplace });
  const { data: installed = [] } = useQuery({ queryKey: ["installed-plugins"], queryFn: edgeAgentsApi.listInstalled });

  const installedIds = new Set(installed.map((i: TenantPlugin) => i.plugin_id));

  const seedMut = useMutation({
    mutationFn: edgeAgentsApi.seedMarketplace,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["marketplace-plugins"] }),
  });

  const installMut = useMutation({
    mutationFn: (id: string) => edgeAgentsApi.installPlugin(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["installed-plugins"] }),
  });

  const uninstallMut = useMutation({
    mutationFn: (id: string) => edgeAgentsApi.uninstallPlugin(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["installed-plugins"] }),
  });

  const categoryColor: Record<string, string> = {
    connector: "bg-blue-900/50 text-blue-300",
    report: "bg-purple-900/50 text-purple-300",
    workflow: "bg-green-900/50 text-green-300",
    alert_rule: "bg-yellow-900/50 text-yellow-300",
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-gray-400 text-sm">Plugins disponíveis para instalação no seu tenant</p>
        {plugins.length === 0 && (
          <button onClick={() => seedMut.mutate()} className="px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm">Carregar Plugins</button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        {plugins.map((p: MarketplacePlugin) => {
          const isInstalled = installedIds.has(p.id);
          return (
            <div key={p.id} className="bg-gray-800 rounded-lg p-4 border border-gray-700 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <span className="font-medium text-white">{p.name}</span>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-xs px-2 py-0.5 rounded ${categoryColor[p.category] || "bg-gray-700 text-gray-300"}`}>{p.category}</span>
                    <span className="text-xs text-gray-500">v{p.version}</span>
                    {p.is_builtin && <span className="text-xs bg-brand-900/50 text-brand-300 px-2 py-0.5 rounded">builtin</span>}
                  </div>
                </div>
                <span className="text-xs text-gray-500">{p.download_count} instalações</span>
              </div>
              {p.description && <p className="text-xs text-gray-400">{p.description}</p>}
              {isInstalled ? (
                <button
                  onClick={() => uninstallMut.mutate(p.id)}
                  className="w-full flex items-center justify-center gap-2 py-2 bg-red-900/30 hover:bg-red-800/30 text-red-300 rounded text-xs font-medium"
                >
                  <X size={12} /> Desinstalar
                </button>
              ) : (
                <button
                  onClick={() => installMut.mutate(p.id)}
                  className="w-full flex items-center justify-center gap-2 py-2 bg-brand-600/30 hover:bg-brand-600/50 text-brand-300 rounded text-xs font-medium"
                >
                  <Download size={12} /> Instalar
                </button>
              )}
            </div>
          );
        })}
      </div>
      {plugins.length === 0 && <p className="text-gray-500 text-sm text-center py-8">Nenhum plugin disponível. Clique em "Carregar Plugins".</p>}
    </div>
  );
}

// ── RBAC Tab ──────────────────────────────────────────────────────────────────

function RbacTab() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", description: "" });

  const { data: roles = [] } = useQuery({ queryKey: ["rbac-roles"], queryFn: edgeAgentsApi.listRoles });

  const createMut = useMutation({
    mutationFn: () => edgeAgentsApi.createRole(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rbac-roles"] }); setShowForm(false); setForm({ name: "", description: "" }); },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => edgeAgentsApi.deleteRole(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rbac-roles"] }),
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-gray-400 text-sm">Roles customizados além dos 3 padrões (admin, analyst, readonly)</p>
        <button onClick={() => setShowForm(v => !v)} className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
          <Plus size={14} /> Nova Role
        </button>
      </div>

      {showForm && (
        <div className="bg-gray-800 rounded-lg p-4 space-y-3 border border-gray-700">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Nome da Role</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="ex: firewall-readonly" className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Descrição</label>
              <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="px-3 py-1.5 text-sm text-gray-400 hover:text-white">Cancelar</button>
            <button onClick={() => createMut.mutate()} disabled={!form.name} className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded text-sm disabled:opacity-50">Salvar</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {roles.map((r: RbacCustomRole) => (
          <div key={r.id} className="bg-gray-800 rounded-lg p-4 flex items-center justify-between border border-gray-700">
            <div>
              <span className="font-medium text-white">{r.name}</span>
              {r.description && <p className="text-xs text-gray-400 mt-0.5">{r.description}</p>}
            </div>
            <button onClick={() => deleteMut.mutate(r.id)} className="p-2 text-gray-500 hover:text-red-400 transition-colors">
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        {roles.length === 0 && <p className="text-gray-500 text-sm text-center py-8">Nenhuma role customizada criada.</p>}
      </div>
    </div>
  );
}
