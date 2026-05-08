import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Edit2, Play, Server, Link, ClipboardList, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { onboardingApi } from "../api/onboarding";
import { identityApi } from "../api/identity";
import type { OnboardingProfile, ExternalConnector, OnboardingProfileSystem } from "../types/onboarding";

const CONNECTOR_LABELS: Record<string, string> = {
  guacamole: "Apache Guacamole",
  tactical_rmm: "Tactical RMM",
  unifi: "Unifi Network",
};

const CONNECTOR_COLORS: Record<string, string> = {
  guacamole: "bg-orange-100 text-orange-700",
  tactical_rmm: "bg-blue-100 text-blue-700",
  unifi: "bg-indigo-100 text-indigo-700",
};

type Tab = "profiles" | "connectors" | "history";

// ── Connector Modal ────────────────────────────────────────────────────────────
function ConnectorModal({ onClose, onSave }: { onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState({ name: "", connector_type: "guacamole", config: {} as Record<string, unknown> });
  const [guac, setGuac] = useState({ url: "", username: "", password: "", verify_ssl: true });
  const [trmm, setTrmm] = useState({ url: "", api_key: "", verify_ssl: true });
  const [unifi, setUnifi] = useState({ url: "", username: "", password: "", site: "default", unifi_os: false, verify_ssl: false });

  const qc = useQueryClient();
  const createMut = useMutation({
    mutationFn: onboardingApi.createConnector,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["onboarding-connectors"] }); onSave(); },
  });

  const getConfig = () => {
    if (form.connector_type === "guacamole") return guac;
    if (form.connector_type === "tactical_rmm") return trmm;
    return unifi;
  };

  const handleSave = () => {
    createMut.mutate({ name: form.name, connector_type: form.connector_type, config: getConfig() as Record<string, unknown> });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">Novo Conector Externo</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
            <input className="w-full border rounded-lg px-3 py-2 text-sm" value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="ex: Guacamole Produção" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tipo</label>
            <select className="w-full border rounded-lg px-3 py-2 text-sm" value={form.connector_type}
              onChange={e => setForm(f => ({ ...f, connector_type: e.target.value }))}>
              <option value="guacamole">Apache Guacamole</option>
              <option value="tactical_rmm">Tactical RMM</option>
              <option value="unifi">Unifi Network</option>
            </select>
          </div>

          {form.connector_type === "guacamole" && (
            <div className="space-y-3 border-t pt-3">
              <p className="text-xs text-gray-500 font-medium">Configuração Guacamole</p>
              <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="URL (ex: http://192.168.1.10/guacamole)"
                value={guac.url} onChange={e => setGuac(g => ({ ...g, url: e.target.value }))} />
              <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="Usuário admin"
                value={guac.username} onChange={e => setGuac(g => ({ ...g, username: e.target.value }))} />
              <input type="password" className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="Senha"
                value={guac.password} onChange={e => setGuac(g => ({ ...g, password: e.target.value }))} />
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={guac.verify_ssl} onChange={e => setGuac(g => ({ ...g, verify_ssl: e.target.checked }))} />
                Verificar SSL
              </label>
            </div>
          )}

          {form.connector_type === "tactical_rmm" && (
            <div className="space-y-3 border-t pt-3">
              <p className="text-xs text-gray-500 font-medium">Configuração Tactical RMM</p>
              <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="URL (ex: https://rmm.empresa.com)"
                value={trmm.url} onChange={e => setTrmm(t => ({ ...t, url: e.target.value }))} />
              <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="API Key"
                value={trmm.api_key} onChange={e => setTrmm(t => ({ ...t, api_key: e.target.value }))} />
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={trmm.verify_ssl} onChange={e => setTrmm(t => ({ ...t, verify_ssl: e.target.checked }))} />
                Verificar SSL
              </label>
            </div>
          )}

          {form.connector_type === "unifi" && (
            <div className="space-y-3 border-t pt-3">
              <p className="text-xs text-gray-500 font-medium">Configuração Unifi Network</p>
              <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="URL (ex: https://192.168.1.1:8443)"
                value={unifi.url} onChange={e => setUnifi(u => ({ ...u, url: e.target.value }))} />
              <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="Usuário admin"
                value={unifi.username} onChange={e => setUnifi(u => ({ ...u, username: e.target.value }))} />
              <input type="password" className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="Senha"
                value={unifi.password} onChange={e => setUnifi(u => ({ ...u, password: e.target.value }))} />
              <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="Site (padrão: default)"
                value={unifi.site} onChange={e => setUnifi(u => ({ ...u, site: e.target.value }))} />
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={unifi.unifi_os} onChange={e => setUnifi(u => ({ ...u, unifi_os: e.target.checked }))} />
                Unifi OS (nova geração UDM)
              </label>
            </div>
          )}
        </div>
        <div className="px-6 py-4 border-t flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50">Cancelar</button>
          <button onClick={handleSave} disabled={createMut.isPending || !form.name}
            className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2">
            {createMut.isPending && <Loader2 size={14} className="animate-spin" />}
            Salvar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Profile Modal ──────────────────────────────────────────────────────────────
function ProfileModal({ profile, connectors, onClose }: {
  profile: OnboardingProfile | null;
  connectors: ExternalConnector[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState(profile?.name ?? "");
  const [desc, setDesc] = useState(profile?.description ?? "");
  const [adGroupInput, setAdGroupInput] = useState("");
  const [adGroups, setAdGroups] = useState<string[]>(profile?.ad_groups ?? []);
  const [systems, setSystems] = useState<OnboardingProfileSystem[]>(profile?.systems ?? []);

  const saveMut = useMutation({
    mutationFn: (data: Omit<OnboardingProfile, "id" | "created_at">) =>
      profile ? onboardingApi.updateProfile(profile.id, data) : onboardingApi.createProfile(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["onboarding-profiles"] }); onClose(); },
  });

  const addAdGroup = () => {
    const g = adGroupInput.trim();
    if (g && !adGroups.includes(g)) {
      setAdGroups(ag => [...ag, g]);
      setAdGroupInput("");
    }
  };

  const addSystem = (connector: ExternalConnector) => {
    if (systems.find(s => s.system_id === connector.id)) return;
    setSystems(ss => [...ss, {
      system_type: connector.connector_type,
      system_id: connector.id,
      system_name: connector.name,
      config: { role: "user", temp_password: "Mudar@123" },
    }]);
  };

  const handleSave = () => {
    saveMut.mutate({ name, description: desc || null, ad_groups: adGroups, systems });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b flex items-center justify-between flex-shrink-0">
          <h2 className="text-lg font-semibold">{profile ? "Editar Perfil" : "Novo Perfil de Cargo"}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
        </div>
        <div className="p-6 space-y-5 overflow-y-auto">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nome do Cargo</label>
              <input className="w-full border rounded-lg px-3 py-2 text-sm" value={name}
                onChange={e => setName(e.target.value)} placeholder="ex: Analista de TI" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Descrição</label>
              <input className="w-full border rounded-lg px-3 py-2 text-sm" value={desc}
                onChange={e => setDesc(e.target.value)} placeholder="Opcional" />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Grupos do Active Directory
              <span className="text-gray-400 font-normal ml-2">— para GLPI, Docs, SysPass e sistemas AD-integrados</span>
            </label>
            <div className="flex gap-2 mb-2">
              <input className="flex-1 border rounded-lg px-3 py-2 text-sm" value={adGroupInput}
                onChange={e => setAdGroupInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && addAdGroup()}
                placeholder="ex: TI-Analistas, VPN-Users" />
              <button onClick={addAdGroup} className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">
                <Plus size={16} />
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {adGroups.map(g => (
                <span key={g} className="flex items-center gap-1 bg-purple-100 text-purple-700 text-xs px-2 py-1 rounded-full">
                  {g}
                  <button onClick={() => setAdGroups(ag => ag.filter(x => x !== g))} className="hover:text-purple-900">×</button>
                </span>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Sistemas Externos</label>
            {connectors.length === 0 ? (
              <p className="text-sm text-gray-400">Nenhum conector externo configurado.</p>
            ) : (
              <div className="space-y-2">
                {connectors.map(c => {
                  const added = systems.find(s => s.system_id === c.id);
                  return (
                    <div key={c.id} className={`flex items-center justify-between p-3 border rounded-lg ${added ? "border-green-300 bg-green-50" : "border-gray-200"}`}>
                      <div className="flex items-center gap-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CONNECTOR_COLORS[c.connector_type]}`}>
                          {CONNECTOR_LABELS[c.connector_type]}
                        </span>
                        <span className="text-sm font-medium">{c.name}</span>
                      </div>
                      {added ? (
                        <button onClick={() => setSystems(ss => ss.filter(s => s.system_id !== c.id))}
                          className="text-xs text-red-600 hover:text-red-800">Remover</button>
                      ) : (
                        <button onClick={() => addSystem(c)} className="text-xs text-brand-600 hover:text-brand-800 font-medium">
                          + Adicionar
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
        <div className="px-6 py-4 border-t flex justify-end gap-3 flex-shrink-0">
          <button onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50">Cancelar</button>
          <button onClick={handleSave} disabled={saveMut.isPending || !name}
            className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2">
            {saveMut.isPending && <Loader2 size={14} className="animate-spin" />}
            Salvar Perfil
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Onboard Modal ──────────────────────────────────────────────────────────────
function OnboardModal({ profiles, onClose }: { profiles: OnboardingProfile[]; onClose: () => void }) {
  const [form, setForm] = useState({ target_username: "", display_name: "", email: "", profile_id: profiles[0]?.id ?? "", notes: "" });
  const [result, setResult] = useState<{ action_id: string; status: string } | null>(null);

  const mut = useMutation({
    mutationFn: onboardingApi.triggerOnboarding,
    onSuccess: (data) => setResult(data),
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">Onboarding com 1 Clique</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
        </div>
        {result ? (
          <div className="p-8 text-center">
            <CheckCircle className="mx-auto text-green-500 mb-3" size={40} />
            <p className="font-semibold text-gray-800">Onboarding iniciado!</p>
            <p className="text-sm text-gray-500 mt-1">ID: {result.action_id}</p>
            <p className="text-sm text-gray-500">Status: {result.status}</p>
            <button onClick={onClose} className="mt-4 px-6 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700">
              Fechar
            </button>
          </div>
        ) : (
          <>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Perfil de Cargo *</label>
                <select className="w-full border rounded-lg px-3 py-2 text-sm" value={form.profile_id}
                  onChange={e => setForm(f => ({ ...f, profile_id: e.target.value }))}>
                  {profiles.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Username *</label>
                <input className="w-full border rounded-lg px-3 py-2 text-sm" value={form.target_username}
                  onChange={e => setForm(f => ({ ...f, target_username: e.target.value }))} placeholder="ex: joao.silva" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Nome Completo</label>
                  <input className="w-full border rounded-lg px-3 py-2 text-sm" value={form.display_name}
                    onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))} placeholder="João Silva" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <input className="w-full border rounded-lg px-3 py-2 text-sm" value={form.email}
                    onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="joao@empresa.com" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Observações</label>
                <textarea className="w-full border rounded-lg px-3 py-2 text-sm" rows={2} value={form.notes}
                  onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="Opcional" />
              </div>
            </div>
            <div className="px-6 py-4 border-t flex justify-end gap-3">
              <button onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50">Cancelar</button>
              <button onClick={() => mut.mutate({ ...form, display_name: form.display_name || undefined, email: form.email || undefined, notes: form.notes || undefined })}
                disabled={mut.isPending || !form.target_username || !form.profile_id}
                className="px-4 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-2">
                {mut.isPending && <Loader2 size={14} className="animate-spin" />}
                Iniciar Onboarding
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export function Onboarding() {
  const [tab, setTab] = useState<Tab>("profiles");
  const [showConnectorModal, setShowConnectorModal] = useState(false);
  const [editingProfile, setEditingProfile] = useState<OnboardingProfile | null | "new">(null);
  const [showOnboardModal, setShowOnboardModal] = useState(false);

  const qc = useQueryClient();

  const { data: profiles = [], isLoading: loadingProfiles } = useQuery({
    queryKey: ["onboarding-profiles"],
    queryFn: onboardingApi.listProfiles,
  });
  const { data: connectors = [], isLoading: loadingConnectors } = useQuery({
    queryKey: ["onboarding-connectors"],
    queryFn: onboardingApi.listConnectors,
  });
  const { data: actions = [] } = useQuery({
    queryKey: ["identity-actions"],
    queryFn: identityApi.listActions,
  });

  const deleteProfile = useMutation({
    mutationFn: onboardingApi.deleteProfile,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["onboarding-profiles"] }),
  });
  const deleteConnector = useMutation({
    mutationFn: onboardingApi.deleteConnector,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["onboarding-connectors"] }),
  });

  const onboardingActions = actions.filter(a => a.action_type === "onboard");

  const STATUS_BADGE: Record<string, string> = {
    pending_discovery: "bg-yellow-100 text-yellow-700",
    pending_approval: "bg-blue-100 text-blue-700",
    running: "bg-indigo-100 text-indigo-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
    cancelled: "bg-gray-100 text-gray-500",
  };

  return (
    <div className="ml-64 min-h-screen bg-gray-50">
      <div className="px-8 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Onboarding</h1>
            <p className="text-sm text-gray-500 mt-1">Perfis de cargo e provisionamento automático em múltiplos sistemas</p>
          </div>
          <button onClick={() => setShowOnboardModal(true)} disabled={profiles.length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium disabled:opacity-50">
            <Play size={16} />
            Onboarding 1 Clique
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b">
          {([["profiles", "Perfis de Cargo", Server], ["connectors", "Conectores Externos", Link], ["history", "Histórico", ClipboardList]] as const).map(([key, label, Icon]) => (
            <button key={key} onClick={() => setTab(key as Tab)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${tab === key ? "border-brand-600 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
              <Icon size={16} />{label}
            </button>
          ))}
        </div>

        {/* Profiles Tab */}
        {tab === "profiles" && (
          <div>
            <div className="flex justify-end mb-4">
              <button onClick={() => setEditingProfile("new")}
                className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm">
                <Plus size={16} /> Novo Perfil
              </button>
            </div>
            {loadingProfiles ? (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-brand-600" size={24} /></div>
            ) : profiles.length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <Server size={40} className="mx-auto mb-3 opacity-30" />
                <p>Nenhum perfil de cargo criado</p>
                <p className="text-sm mt-1">Crie um perfil para definir quais sistemas cada cargo tem acesso</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {profiles.map(p => (
                  <div key={p.id} className="bg-white border rounded-xl p-5">
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="font-semibold text-gray-900">{p.name}</h3>
                        {p.description && <p className="text-sm text-gray-500 mt-0.5">{p.description}</p>}
                      </div>
                      <div className="flex gap-2">
                        <button onClick={() => setEditingProfile(p)} className="p-1.5 text-gray-400 hover:text-brand-600 rounded">
                          <Edit2 size={15} />
                        </button>
                        <button onClick={() => deleteProfile.mutate(p.id)} className="p-1.5 text-gray-400 hover:text-red-600 rounded">
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {p.ad_groups.map(g => (
                        <span key={g} className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">{g}</span>
                      ))}
                      {p.systems.map(s => (
                        <span key={s.system_id} className={`text-xs px-2 py-0.5 rounded-full ${CONNECTOR_COLORS[s.system_type] || "bg-gray-100 text-gray-600"}`}>
                          {CONNECTOR_LABELS[s.system_type] || s.system_type}: {s.system_name}
                        </span>
                      ))}
                      {p.ad_groups.length === 0 && p.systems.length === 0 && (
                        <span className="text-xs text-gray-400">Sem sistemas configurados</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Connectors Tab */}
        {tab === "connectors" && (
          <div>
            <div className="flex justify-end mb-4">
              <button onClick={() => setShowConnectorModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm">
                <Plus size={16} /> Novo Conector
              </button>
            </div>
            {loadingConnectors ? (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-brand-600" size={24} /></div>
            ) : connectors.length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <Link size={40} className="mx-auto mb-3 opacity-30" />
                <p>Nenhum conector configurado</p>
                <p className="text-sm mt-1">Adicione Guacamole, Tactical RMM ou Unifi</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3">
                {connectors.map(c => (
                  <div key={c.id} className="bg-white border rounded-xl p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className={`text-xs px-2 py-1 rounded-full font-medium ${CONNECTOR_COLORS[c.connector_type] || "bg-gray-100 text-gray-600"}`}>
                        {CONNECTOR_LABELS[c.connector_type] || c.connector_type}
                      </span>
                      <span className="font-medium text-sm">{c.name}</span>
                    </div>
                    <button onClick={() => deleteConnector.mutate(c.id)} className="p-1.5 text-gray-400 hover:text-red-600 rounded">
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* History Tab */}
        {tab === "history" && (
          <div className="space-y-3">
            {onboardingActions.length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <ClipboardList size={40} className="mx-auto mb-3 opacity-30" />
                <p>Nenhum onboarding realizado</p>
              </div>
            ) : onboardingActions.map(a => (
              <div key={a.id} className="bg-white border rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium text-sm">{a.target_username}</span>
                    {a.display_name && <span className="text-gray-500 text-sm ml-2">({a.display_name})</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[a.status] || "bg-gray-100 text-gray-500"}`}>
                      {a.status}
                    </span>
                    <span className="text-xs text-gray-400">{new Date(a.created_at).toLocaleDateString("pt-BR")}</span>
                  </div>
                </div>
                {a.tasks.length > 0 && (
                  <div className="mt-3 space-y-1">
                    {a.tasks.map((t: { id: string; status: string; system_name: string; result?: string; error?: string }) => (
                      <div key={t.id} className="flex items-center gap-2 text-xs text-gray-600">
                        {t.status === "success" ? <CheckCircle size={12} className="text-green-500" /> :
                         t.status === "failed" ? <XCircle size={12} className="text-red-500" /> :
                         <Loader2 size={12} className="animate-spin text-gray-400" />}
                        <span>{t.system_name}</span>
                        {t.result && <span className="text-gray-400">— {t.result}</span>}
                        {t.error && <span className="text-red-500">— {t.error}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {showConnectorModal && <ConnectorModal onClose={() => setShowConnectorModal(false)} onSave={() => setShowConnectorModal(false)} />}
      {editingProfile !== null && (
        <ProfileModal
          profile={editingProfile === "new" ? null : editingProfile}
          connectors={connectors}
          onClose={() => setEditingProfile(null)}
        />
      )}
      {showOnboardModal && <OnboardModal profiles={profiles} onClose={() => setShowOnboardModal(false)} />}
    </div>
  );
}
