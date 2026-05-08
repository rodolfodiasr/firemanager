import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock,
  Globe,
  Loader2,
  Lock,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  UserCheck,
  UserMinus,
  UserX,
  X,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { identityApi } from "../api/identity";
import type {
  ActionStatus,
  IdentityProvider,
  IdentityUser,
  LifecycleAction,
  LifecycleTask,
  OrphanUser,
  ProviderType,
  TaskStatus,
} from "../types/identity";

// ── Constants ──────────────────────────────────────────────────────────────────

const PROVIDER_LABELS: Record<ProviderType, string> = {
  azure_ad: "Azure AD / Entra ID",
  google_workspace: "Google Workspace",
};

const PROVIDER_COLORS: Record<ProviderType, string> = {
  azure_ad: "bg-blue-100 text-blue-700",
  google_workspace: "bg-red-100 text-red-700",
};

const SYSTEM_LABELS: Record<string, string> = {
  azure_ad: "Azure AD",
  google_workspace: "Google Workspace",
  ssh_linux: "Linux SSH",
  winrm_windows: "Windows WinRM",
  database: "Banco de Dados",
};

const STATUS_STYLE: Record<ActionStatus, string> = {
  pending_discovery: "bg-yellow-100 text-yellow-700",
  pending_approval:  "bg-orange-100 text-orange-700",
  running:           "bg-blue-100 text-blue-700",
  completed:         "bg-green-100 text-green-700",
  failed:            "bg-red-100 text-red-700",
  cancelled:         "bg-gray-100 text-gray-500",
};

const STATUS_LABELS: Record<ActionStatus, string> = {
  pending_discovery: "Descobrindo acessos…",
  pending_approval:  "Aguardando aprovação",
  running:           "Executando…",
  completed:         "Concluído",
  failed:            "Falhou",
  cancelled:         "Cancelado",
};

const TASK_STATUS_ICON: Record<TaskStatus, React.ReactNode> = {
  pending:   <Clock size={14} className="text-gray-400" />,
  running:   <Loader2 size={14} className="text-blue-500 animate-spin" />,
  success:   <CheckCircle2 size={14} className="text-green-500" />,
  failed:    <AlertCircle size={14} className="text-red-500" />,
  skipped:   <AlertTriangle size={14} className="text-yellow-500" />,
  not_found: <AlertTriangle size={14} className="text-gray-400" />,
};

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

// ── Provider Modal ─────────────────────────────────────────────────────────────

function ProviderModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [type, setType] = useState<ProviderType>("azure_ad");

  // Azure AD fields
  const [azureTenantId, setAzureTenantId] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");

  // Google Workspace fields
  const [serviceAccountJson, setServiceAccountJson] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [domain, setDomain] = useState("");

  const mut = useMutation({
    mutationFn: (config: Record<string, unknown>) =>
      identityApi.createProvider({ name, provider_type: type, config }),
    onSuccess: () => {
      toast.success("Provedor adicionado");
      qc.invalidateQueries({ queryKey: ["identity-providers"] });
      onClose();
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Erro ao salvar"),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    let config: Record<string, unknown>;
    if (type === "azure_ad") {
      config = { azure_tenant_id: azureTenantId, client_id: clientId, client_secret: clientSecret };
    } else {
      let sa: unknown;
      try {
        sa = JSON.parse(serviceAccountJson);
      } catch {
        toast.error("JSON da conta de serviço inválido");
        return;
      }
      config = { service_account: sa, admin_email: adminEmail, domain };
    }
    mut.mutate(config);
  }

  const inputCls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none";
  const labelCls = "text-xs font-medium text-gray-600 mb-1 block";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">Adicionar Provedor de Identidade</h2>
          <button onClick={onClose}><X size={20} className="text-gray-400 hover:text-gray-600" /></button>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          <div>
            <label className={labelCls}>Nome *</label>
            <input required value={name} onChange={(e) => setName(e.target.value)} className={inputCls} placeholder="Ex: Azure AD Corporativo" />
          </div>
          <div>
            <label className={labelCls}>Tipo *</label>
            <select value={type} onChange={(e) => setType(e.target.value as ProviderType)} className={inputCls + " bg-white"}>
              <option value="azure_ad">Azure AD / Entra ID</option>
              <option value="google_workspace">Google Workspace</option>
            </select>
          </div>

          {type === "azure_ad" ? (
            <>
              <div>
                <label className={labelCls}>Azure Tenant ID *</label>
                <input required value={azureTenantId} onChange={(e) => setAzureTenantId(e.target.value)} className={inputCls} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
              </div>
              <div>
                <label className={labelCls}>Client ID (App Registration) *</label>
                <input required value={clientId} onChange={(e) => setClientId(e.target.value)} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Client Secret *</label>
                <input required type="password" value={clientSecret} onChange={(e) => setClientSecret(e.target.value)} className={inputCls} />
              </div>
              <p className="text-xs text-gray-500">Permissões necessárias: <code>User.Read.All</code>, <code>User.ReadWrite.All</code>, <code>Directory.Read.All</code></p>
            </>
          ) : (
            <>
              <div>
                <label className={labelCls}>Service Account JSON *</label>
                <textarea required rows={5} value={serviceAccountJson} onChange={(e) => setServiceAccountJson(e.target.value)} className={inputCls + " font-mono text-xs"} placeholder='{"type":"service_account","client_email":"...","private_key":"..."}' />
              </div>
              <div>
                <label className={labelCls}>Email do Admin (delegação) *</label>
                <input required value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} className={inputCls} placeholder="admin@empresa.com" />
              </div>
              <div>
                <label className={labelCls}>Domínio *</label>
                <input required value={domain} onChange={(e) => setDomain(e.target.value)} className={inputCls} placeholder="empresa.com" />
              </div>
            </>
          )}

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 border border-gray-300 rounded-lg py-2 text-sm hover:bg-gray-50">Cancelar</button>
            <button type="submit" disabled={mut.isPending} className="flex-1 bg-brand-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-60 flex items-center justify-center gap-2">
              {mut.isPending && <Loader2 size={14} className="animate-spin" />}Salvar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Offboard Modal ─────────────────────────────────────────────────────────────

function OffboardModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [notes, setNotes] = useState("");

  const mut = useMutation({
    mutationFn: () =>
      identityApi.createAction({
        target_username: username,
        display_name: displayName || undefined,
        email: email || undefined,
        notes: notes || undefined,
      }),
    onSuccess: () => {
      toast.success("Offboarding iniciado — descobrindo acessos…");
      qc.invalidateQueries({ queryKey: ["identity-actions"] });
      onClose();
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Erro ao iniciar"),
  });

  const inputCls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none";
  const labelCls = "text-xs font-medium text-gray-600 mb-1 block";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-red-700 flex items-center gap-2">
            <UserMinus size={20} /> Iniciar Offboarding
          </h2>
          <button onClick={onClose}><X size={20} className="text-gray-400" /></button>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); mut.mutate(); }} className="px-6 py-4 space-y-4">
          <div>
            <label className={labelCls}>Username / UPN / Email *</label>
            <input required value={username} onChange={(e) => setUsername(e.target.value)} className={inputCls} placeholder="joao.silva ou joao@empresa.com" />
          </div>
          <div>
            <label className={labelCls}>Nome completo</label>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>E-mail</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Observações</label>
            <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} className={inputCls} placeholder="Motivo do desligamento, ticket RH…" />
          </div>
          <p className="text-xs text-gray-500">A plataforma vai descobrir automaticamente todos os acessos deste usuário nos sistemas conectados.</p>
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 border border-gray-300 rounded-lg py-2 text-sm hover:bg-gray-50">Cancelar</button>
            <button type="submit" disabled={mut.isPending} className="flex-1 bg-red-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60 flex items-center justify-center gap-2">
              {mut.isPending && <Loader2 size={14} className="animate-spin" />}Iniciar Offboarding
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Action Detail ──────────────────────────────────────────────────────────────

function ActionDetail({ action, onClose }: { action: LifecycleAction; onClose: () => void }) {
  const qc = useQueryClient();

  const { data: fresh = action } = useQuery({
    queryKey: ["identity-action", action.id],
    queryFn: () => identityApi.getAction(action.id),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "pending_discovery" || s === "running" ? 2000 : false;
    },
  });

  const approveMut = useMutation({
    mutationFn: () => identityApi.approveAction(action.id),
    onSuccess: () => {
      toast.success("Revogação iniciada");
      qc.invalidateQueries({ queryKey: ["identity-action", action.id] });
      qc.invalidateQueries({ queryKey: ["identity-actions"] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Erro"),
  });

  const cancelMut = useMutation({
    mutationFn: () => identityApi.cancelAction(action.id),
    onSuccess: () => {
      toast.success("Cancelado");
      qc.invalidateQueries({ queryKey: ["identity-actions"] });
      onClose();
    },
  });

  const done = ["completed", "failed", "cancelled"].includes(fresh.status);
  const successCount = fresh.tasks.filter((t) => t.status === "success").length;
  const failCount = fresh.tasks.filter((t) => t.status === "failed").length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="text-lg font-semibold">Offboarding — {fresh.target_username}</h2>
            {fresh.display_name && <p className="text-sm text-gray-500">{fresh.display_name}</p>}
          </div>
          <button onClick={onClose}><X size={20} className="text-gray-400" /></button>
        </div>

        <div className="px-6 py-4 overflow-y-auto flex-1 space-y-4">
          {/* Status */}
          <div className="flex items-center gap-3">
            <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${STATUS_STYLE[fresh.status]}`}>
              {STATUS_LABELS[fresh.status]}
            </span>
            {fresh.notes && <span className="text-sm text-gray-500 italic">{fresh.notes}</span>}
          </div>

          {/* Summary row when done */}
          {done && fresh.tasks.length > 0 && (
            <div className="flex gap-4 text-sm">
              <span className="text-green-600 font-medium">✓ {successCount} sistemas revogados</span>
              {failCount > 0 && <span className="text-red-600 font-medium">✗ {failCount} falharam</span>}
            </div>
          )}

          {/* Discovery pending */}
          {fresh.status === "pending_discovery" && (
            <div className="flex items-center gap-2 text-sm text-yellow-700 bg-yellow-50 px-4 py-3 rounded-lg">
              <Loader2 size={16} className="animate-spin" />
              Verificando acessos nos sistemas conectados…
            </div>
          )}

          {/* No accesses found */}
          {fresh.status === "pending_approval" && fresh.tasks.length === 0 && (
            <div className="text-sm text-gray-500 bg-gray-50 px-4 py-3 rounded-lg">
              Nenhum acesso encontrado nos sistemas conectados.
            </div>
          )}

          {/* Tasks list */}
          {fresh.tasks.length > 0 && (
            <div className="border rounded-lg overflow-hidden">
              <div className="bg-gray-50 px-4 py-2 text-xs font-semibold text-gray-500 uppercase">
                Acessos encontrados / resultado
              </div>
              <div className="divide-y">
                {fresh.tasks.map((task) => (
                  <div key={task.id} className="px-4 py-3 flex items-start gap-3">
                    <div className="mt-0.5">{TASK_STATUS_ICON[task.status]}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{task.system_name}</span>
                        <span className="text-xs text-gray-400">{SYSTEM_LABELS[task.system_type] ?? task.system_type}</span>
                      </div>
                      {task.result && <p className="text-xs text-green-600 mt-0.5">{task.result}</p>}
                      {task.error && <p className="text-xs text-red-600 mt-0.5">{task.error}</p>}
                      {task.executed_at && (
                        <p className="text-xs text-gray-400 mt-0.5">{fmtDate(task.executed_at)}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="px-6 py-4 border-t flex gap-3">
          {fresh.status === "pending_approval" && (
            <>
              <button
                onClick={() => cancelMut.mutate()}
                disabled={cancelMut.isPending}
                className="border border-gray-300 rounded-lg px-4 py-2 text-sm hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={() => approveMut.mutate()}
                disabled={approveMut.isPending}
                className="flex-1 bg-red-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {approveMut.isPending && <Loader2 size={14} className="animate-spin" />}
                {fresh.tasks.length === 0
                  ? "Confirmar (nenhum acesso)"
                  : `Aprovar e Revogar ${fresh.tasks.length} acesso${fresh.tasks.length > 1 ? "s" : ""}`}
              </button>
            </>
          )}
          {(done || fresh.status === "running") && (
            <button onClick={onClose} className="ml-auto border border-gray-300 rounded-lg px-4 py-2 text-sm hover:bg-gray-50">Fechar</button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Tab: Provedores ────────────────────────────────────────────────────────────

function TabProviders() {
  const qc = useQueryClient();
  const [showModal, setShowModal] = useState(false);

  const { data: providers = [], isLoading } = useQuery({
    queryKey: ["identity-providers"],
    queryFn: identityApi.listProviders,
  });

  const deleteMut = useMutation({
    mutationFn: identityApi.deleteProvider,
    onSuccess: () => { toast.success("Removido"); qc.invalidateQueries({ queryKey: ["identity-providers"] }); },
  });

  const syncMut = useMutation({
    mutationFn: identityApi.syncProvider,
    onSuccess: (p) => {
      toast.success(`${p.last_sync_count} usuários sincronizados`);
      qc.invalidateQueries({ queryKey: ["identity-providers"] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Erro na sincronização"),
  });

  if (isLoading) return <div className="flex justify-center py-20"><Loader2 size={24} className="animate-spin text-gray-400" /></div>;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-700"
        >
          <Plus size={16} /> Adicionar Provedor
        </button>
      </div>

      {providers.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Globe size={40} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">Nenhum provedor configurado.</p>
          <p className="text-xs mt-1">Adicione Azure AD ou Google Workspace para sincronizar usuários.</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {providers.map((p) => (
            <div key={p.id} className="border rounded-xl p-4 bg-white flex items-center gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-sm">{p.name}</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${PROVIDER_COLORS[p.provider_type]}`}>
                    {PROVIDER_LABELS[p.provider_type]}
                  </span>
                </div>
                <div className="text-xs text-gray-500">
                  {p.last_sync_at
                    ? `Última sync: ${fmtDate(p.last_sync_at)} · ${p.last_sync_count ?? 0} usuários`
                    : "Nunca sincronizado"}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => syncMut.mutate(p.id)}
                  disabled={syncMut.isPending && syncMut.variables === p.id}
                  className="flex items-center gap-1 border border-gray-300 rounded-lg px-3 py-1.5 text-xs hover:bg-gray-50 disabled:opacity-60"
                >
                  <RefreshCw size={13} className={syncMut.isPending ? "animate-spin" : ""} />
                  Sincronizar
                </button>
                <button
                  onClick={() => {
                    if (confirm("Remover este provedor e todos os usuários sincronizados?"))
                      deleteMut.mutate(p.id);
                  }}
                  className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && <ProviderModal onClose={() => setShowModal(false)} />}
    </div>
  );
}

// ── Tab: Diretório ─────────────────────────────────────────────────────────────

function TabDirectory() {
  const { data: providers = [] } = useQuery({
    queryKey: ["identity-providers"],
    queryFn: identityApi.listProviders,
  });

  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [search, setSearch] = useState("");

  const { data: users = [], isLoading } = useQuery({
    queryKey: ["identity-users", selectedProvider],
    queryFn: () => identityApi.listUsers(selectedProvider),
    enabled: !!selectedProvider,
  });

  const filtered = users.filter((u) => {
    const q = search.toLowerCase();
    return (
      u.username.toLowerCase().includes(q) ||
      (u.display_name ?? "").toLowerCase().includes(q) ||
      (u.email ?? "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <select
          value={selectedProvider}
          onChange={(e) => setSelectedProvider(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
        >
          <option value="">Selecione um provedor…</option>
          {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        {selectedProvider && (
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar usuário…"
              className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none"
            />
          </div>
        )}
      </div>

      {!selectedProvider ? (
        <div className="text-center py-12 text-gray-400 text-sm">Selecione um provedor para ver os usuários sincronizados.</div>
      ) : isLoading ? (
        <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-gray-400" /></div>
      ) : (
        <div className="border rounded-xl overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3 text-left">Usuário</th>
                <th className="px-4 py-3 text-left">Email</th>
                <th className="px-4 py-3 text-left">Departamento</th>
                <th className="px-4 py-3 text-left">Último login</th>
                <th className="px-4 py-3 text-left">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{u.display_name ?? u.username}</div>
                    <div className="text-xs text-gray-400">{u.username}</div>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{u.email ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-600">{u.department ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-500">{u.last_sign_in_raw ? fmtDate(u.last_sign_in_raw) : "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${u.is_enabled ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                      {u.is_enabled ? "Ativo" : "Desabilitado"}
                    </span>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Nenhum usuário encontrado.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Tab: Offboarding ───────────────────────────────────────────────────────────

function TabOffboarding() {
  const qc = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [selected, setSelected] = useState<LifecycleAction | null>(null);

  const { data: actions = [], isLoading } = useQuery({
    queryKey: ["identity-actions"],
    queryFn: identityApi.listActions,
    refetchInterval: (q) => {
      const active = q.state.data?.some((a) =>
        a.status === "pending_discovery" || a.status === "running"
      );
      return active ? 3000 : 30000;
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700"
        >
          <UserMinus size={16} /> Iniciar Offboarding
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-gray-400" /></div>
      ) : actions.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <UserMinus size={40} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">Nenhum offboarding registrado.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {actions.map((a) => (
            <button
              key={a.id}
              onClick={() => setSelected(a)}
              className="w-full text-left border rounded-xl p-4 bg-white hover:border-brand-400 hover:shadow-sm transition-all flex items-center gap-4"
            >
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-sm">{a.display_name ?? a.target_username}</span>
                  {a.display_name && <span className="text-xs text-gray-400">{a.target_username}</span>}
                  {a.status === "pending_discovery" && <Loader2 size={12} className="animate-spin text-yellow-500" />}
                  {a.status === "running" && <Loader2 size={12} className="animate-spin text-blue-500" />}
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  <span className={`px-2 py-0.5 rounded-full font-semibold ${STATUS_STYLE[a.status]}`}>{STATUS_LABELS[a.status]}</span>
                  {a.tasks.length > 0 && <span>{a.tasks.length} sistema{a.tasks.length > 1 ? "s" : ""}</span>}
                  <span>{fmtDate(a.created_at)}</span>
                </div>
              </div>
              <ChevronRight size={16} className="text-gray-400 shrink-0" />
            </button>
          ))}
        </div>
      )}

      {showModal && <OffboardModal onClose={() => setShowModal(false)} />}
      {selected && <ActionDetail action={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

// ── Tab: Contas Órfãs ──────────────────────────────────────────────────────────

function TabOrphans() {
  const { data: orphans = [], isLoading, refetch } = useQuery({
    queryKey: ["identity-orphans"],
    queryFn: identityApi.listOrphans,
  });
  const [search, setSearch] = useState("");

  const filtered = orphans.filter((o) => {
    const q = search.toLowerCase();
    return (
      o.username.toLowerCase().includes(q) ||
      (o.display_name ?? "").toLowerCase().includes(q) ||
      (o.email ?? "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar conta…"
            className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none"
          />
        </div>
        <button onClick={() => refetch()} className="flex items-center gap-1 border border-gray-300 rounded-lg px-3 py-2 text-sm hover:bg-gray-50">
          <RefreshCw size={14} /> Atualizar
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-gray-400" /></div>
      ) : (
        <>
          {orphans.length > 0 && (
            <div className="flex items-center gap-2 bg-orange-50 border border-orange-200 rounded-lg px-4 py-2 text-sm text-orange-700">
              <AlertTriangle size={16} />
              {orphans.length} conta{orphans.length > 1 ? "s desabilitadas" : " desabilitada"} encontrada{orphans.length > 1 ? "s" : ""} — verifique se deve iniciar offboarding.
            </div>
          )}
          <div className="border rounded-xl overflow-hidden bg-white">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3 text-left">Usuário</th>
                  <th className="px-4 py-3 text-left">Provedor</th>
                  <th className="px-4 py-3 text-left">Departamento</th>
                  <th className="px-4 py-3 text-left">Último login</th>
                  <th className="px-4 py-3 text-left">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map((o, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{o.display_name ?? o.username}</div>
                      <div className="text-xs text-gray-400">{o.email ?? o.username}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${PROVIDER_COLORS[o.provider_type]}`}>
                        {PROVIDER_LABELS[o.provider_type]}
                      </span>
                      <div className="text-xs text-gray-400 mt-0.5">{o.provider_name}</div>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{o.department ?? "—"}</td>
                    <td className="px-4 py-3 text-gray-500">{o.last_sign_in_raw ? fmtDate(o.last_sign_in_raw) : "—"}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-600">Desabilitada</span>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                    {orphans.length === 0 ? "Nenhuma conta órfã encontrada. Sincronize os provedores primeiro." : "Nenhum resultado para a busca."}
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────

const TABS = [
  { id: "providers", label: "Provedores", icon: Globe },
  { id: "directory", label: "Diretório", icon: UserCheck },
  { id: "offboarding", label: "Offboarding", icon: UserMinus },
  { id: "orphans", label: "Contas Órfãs", icon: UserX },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function Identity() {
  const [tab, setTab] = useState<TabId>("providers");

  return (
    <PageWrapper
      title="Gestão de Identidade e Ciclo de Vida"
      subtitle="Provedores de diretório, offboarding coordenado e contas órfãs"
    >
      {/* Tab bar */}
      <div className="flex border-b mb-6 gap-1">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg border-b-2 transition-colors ${
              tab === id
                ? "border-brand-600 text-brand-600 bg-brand-50"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50"
            }`}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      {tab === "providers"   && <TabProviders />}
      {tab === "directory"   && <TabDirectory />}
      {tab === "offboarding" && <TabOffboarding />}
      {tab === "orphans"     && <TabOrphans />}
    </PageWrapper>
  );
}
