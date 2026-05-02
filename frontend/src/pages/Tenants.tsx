import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Plus,
  UserPlus,
  Trash2,
  Edit2,
  Check,
  X,
  ChevronRight,
  KeyRound,
  ToggleLeft,
  ToggleRight,
  Users,
  ShieldCheck,
} from "lucide-react";
import { tenantsApi } from "../api/tenants";
import { inviteApi } from "../api/invite";
import { permissionsApi, type DeviceCategory, type FunctionalModule, type UserPermissionProfile } from "../api/permissions";
import { useAuth } from "../hooks/useAuth";
import { TopBar } from "../components/layout/TopBar";
import type { TenantMember, TenantRead, TenantRole } from "../types/tenant";

const ROLES: TenantRole[] = ["admin", "analyst_n2", "analyst_n1", "readonly"];
const ROLE_LABELS: Record<TenantRole, string> = {
  admin:       "Admin",
  analyst_n2:  "Analista N2",
  analyst_n1:  "Analista N1",
  readonly:    "Leitor",
  analyst:     "Analista (legado)",
};
const ROLE_COLORS: Record<TenantRole, string> = {
  admin:       "bg-brand-100 text-brand-700",
  analyst_n2:  "bg-blue-100 text-blue-700",
  analyst_n1:  "bg-cyan-100 text-cyan-700",
  readonly:    "bg-gray-100 text-gray-600",
  analyst:     "bg-blue-100 text-blue-600",
};

function RoleBadge({ role }: { role: TenantRole }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${ROLE_COLORS[role]}`}>
      {ROLE_LABELS[role]}
    </span>
  );
}

// ── Permission Matrix ─────────────────────────────────────────────────────────

const DEVICE_CATS: { key: DeviceCategory; label: string }[] = [
  { key: "firewall", label: "Firewall" },
  { key: "switch",   label: "Switch / Roteador" },
  { key: "server",   label: "Servidor" },
  { key: "hypervisor", label: "Hypervisor" },
];

const FUNC_MODULES: { key: FunctionalModule; label: string }[] = [
  { key: "compliance",      label: "Compliance" },
  { key: "remediation",     label: "Remediação" },
  { key: "server_analysis", label: "Análise de Servidores" },
  { key: "bulk_jobs",       label: "Jobs em Lote" },
];

const PERM_ROLES: { value: TenantRole | ""; label: string }[] = [
  { value: "", label: "— (herdar)" },
  { value: "admin", label: "Admin" },
  { value: "analyst_n2", label: "Analista N2" },
  { value: "analyst_n1", label: "Analista N1" },
  { value: "readonly", label: "Leitor" },
];

interface PermissionMatrixDrawerProps {
  tenantId: string;
  userId: string;
  userName: string;
  onClose: () => void;
}

function PermissionMatrixDrawer({ tenantId, userId, userName, onClose }: PermissionMatrixDrawerProps) {
  const qc = useQueryClient();

  const { data: profile, isLoading } = useQuery({
    queryKey: ["perm-profile", tenantId, userId],
    queryFn: () => permissionsApi.getUserModuleProfile(userId),
  });

  const upsertCat = useMutation({
    mutationFn: ({ cat, role }: { cat: DeviceCategory; role: TenantRole }) =>
      permissionsApi.upsertCategoryRole(userId, cat, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["perm-profile", tenantId, userId] }),
  });

  const deleteCat = useMutation({
    mutationFn: (cat: DeviceCategory) => permissionsApi.deleteCategoryRole(userId, cat),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["perm-profile", tenantId, userId] }),
  });

  const upsertMod = useMutation({
    mutationFn: ({ mod, role }: { mod: FunctionalModule; role: TenantRole }) =>
      permissionsApi.upsertModuleRole(userId, mod, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["perm-profile", tenantId, userId] }),
  });

  const deleteMod = useMutation({
    mutationFn: (mod: FunctionalModule) => permissionsApi.deleteModuleRole(userId, mod),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["perm-profile", tenantId, userId] }),
  });

  const getCatOverride = (cat: DeviceCategory): TenantRole | "" => {
    const found = profile?.category_roles.find((cr) => cr.category === cat);
    return found ? found.role : "";
  };

  const getModOverride = (mod: FunctionalModule): TenantRole | "" => {
    const found = profile?.module_roles.find((mr) => mr.module === mod);
    return found ? found.role : "";
  };

  const handleCatChange = (cat: DeviceCategory, val: TenantRole | "") => {
    if (val === "") {
      deleteCat.mutate(cat);
    } else {
      upsertCat.mutate({ cat, role: val });
    }
  };

  const handleModChange = (mod: FunctionalModule, val: TenantRole | "") => {
    if (val === "") {
      deleteMod.mutate(mod);
    } else {
      upsertMod.mutate({ mod, role: val });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-white shadow-2xl flex flex-col h-full overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 shrink-0">
          <div className="flex items-center gap-2">
            <ShieldCheck size={18} className="text-brand-600" />
            <h2 className="text-base font-semibold text-gray-900">Permissões — {userName}</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        {isLoading ? (
          <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">Carregando...</div>
        ) : (
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
            {profile && (
              <div className="bg-gray-50 rounded-lg px-3 py-2 text-xs text-gray-500">
                Perfil global: <span className="font-semibold text-gray-700">{ROLE_LABELS[profile.tenant_role] ?? profile.tenant_role}</span>
                <span className="ml-2 text-gray-400">— overrides abaixo substituem este valor por módulo</span>
              </div>
            )}

            {/* Device Categories */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Categorias de Dispositivo</p>
              <table className="w-full text-sm">
                <tbody className="divide-y divide-gray-100">
                  {DEVICE_CATS.map(({ key, label }) => {
                    const override = getCatOverride(key);
                    return (
                      <tr key={key} className="hover:bg-gray-50">
                        <td className="py-2.5 pr-4 text-gray-700">{label}</td>
                        <td className="py-2.5">
                          <select
                            value={override}
                            onChange={(e) => handleCatChange(key, e.target.value as TenantRole | "")}
                            className={`border rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500 ${
                              override ? "border-brand-300 bg-brand-50 text-brand-700" : "border-gray-200 text-gray-500"
                            }`}
                          >
                            {PERM_ROLES.map((r) => (
                              <option key={r.value} value={r.value}>{r.label}</option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Functional Modules */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Módulos Funcionais</p>
              <table className="w-full text-sm">
                <tbody className="divide-y divide-gray-100">
                  {FUNC_MODULES.map(({ key, label }) => {
                    const override = getModOverride(key);
                    return (
                      <tr key={key} className="hover:bg-gray-50">
                        <td className="py-2.5 pr-4 text-gray-700">{label}</td>
                        <td className="py-2.5">
                          <select
                            value={override}
                            onChange={(e) => handleModChange(key, e.target.value as TenantRole | "")}
                            className={`border rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500 ${
                              override ? "border-brand-300 bg-brand-50 text-brand-700" : "border-gray-200 text-gray-500"
                            }`}
                          >
                            {PERM_ROLES.map((r) => (
                              <option key={r.value} value={r.value}>{r.label}</option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Members panel ────────────────────────────────────────────────────────────

interface MembersPanelProps {
  tenantId: string;
  tenantName: string;
  currentUserId: string;
}

function MembersPanel({ tenantId, tenantName, currentUserId }: MembersPanelProps) {
  const qc = useQueryClient();
  const [showInvite, setShowInvite] = useState(false);
  const [inviteMode, setInviteMode] = useState<"direct" | "email">("direct");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteRole, setInviteRole] = useState<TenantRole>("analyst_n2");
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [emailSent, setEmailSent] = useState(false);
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editRole, setEditRole] = useState<TenantRole>("analyst_n2");
  const [permUserId, setPermUserId] = useState<string | null>(null);
  const [permUserName, setPermUserName] = useState("");

  const { data: members = [], isLoading } = useQuery({
    queryKey: ["members", tenantId],
    queryFn: () => tenantsApi.listMembers(tenantId),
  });

  const inviteMut = useMutation({
    mutationFn: async () => {
      if (inviteMode === "direct") {
        return tenantsApi.inviteByEmail(tenantId, { email: inviteEmail, name: inviteName || undefined, role: inviteRole });
      }
      await inviteApi.create({ email: inviteEmail, tenant_id: tenantId, role: inviteRole, frontend_url: window.location.origin });
      setEmailSent(true);
      return { member: null as unknown as TenantMember, temp_password: null as string | null };
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["members", tenantId] });
      if (res?.temp_password) setTempPassword(res.temp_password);
      if (inviteMode === "direct") {
        setShowInvite(false);
        setInviteEmail("");
        setInviteName("");
        setInviteRole("analyst_n2");
      }
    },
  });

  const updateRoleMut = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: TenantRole }) =>
      tenantsApi.updateMemberRole(tenantId, userId, role),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["members", tenantId] });
      setEditingUserId(null);
    },
  });

  const removeMut = useMutation({
    mutationFn: (userId: string) => tenantsApi.removeMember(tenantId, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["members", tenantId] }),
  });

  return (
    <div className="flex flex-col h-full">
      {permUserId && (
        <PermissionMatrixDrawer
          tenantId={tenantId}
          userId={permUserId}
          userName={permUserName}
          onClose={() => setPermUserId(null)}
        />
      )}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Users size={16} className="text-brand-500" />
          <span className="text-sm font-semibold text-gray-700">{tenantName}</span>
        </div>
        <button
          onClick={() => { setShowInvite(true); setTempPassword(null); setEmailSent(false); }}
          className="flex items-center gap-1.5 text-xs font-medium bg-brand-600 text-white px-3 py-1.5 rounded-lg hover:bg-brand-700 transition-colors"
        >
          <UserPlus size={13} />
          Convidar
        </button>
      </div>

      {tempPassword && (
        <div className="mb-3 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5 text-xs">
          <div className="flex items-center gap-1.5 font-semibold text-amber-800 mb-1">
            <KeyRound size={13} />
            Novo usuário criado — senha temporária:
          </div>
          <code className="font-mono text-amber-900 select-all">{tempPassword}</code>
          <p className="text-amber-700 mt-1">Anote a senha — ela não será exibida novamente.</p>
          <button onClick={() => setTempPassword(null)} className="text-amber-600 hover:text-amber-800 mt-1 underline">
            Fechar
          </button>
        </div>
      )}

      {showInvite && emailSent && (
        <div className="mb-3 bg-green-50 border border-green-200 rounded-xl p-3 text-xs text-green-800">
          <p className="font-semibold mb-1">Convite enviado!</p>
          <p>Um e-mail foi enviado para <strong>{inviteEmail}</strong> com o link de acesso.</p>
          <button
            onClick={() => { setEmailSent(false); setShowInvite(false); setInviteEmail(""); setInviteRole("analyst_n2"); }}
            className="mt-2 text-green-600 underline"
          >
            Fechar
          </button>
        </div>
      )}
      {showInvite && !emailSent && (
        <div className="mb-3 bg-gray-50 border border-gray-200 rounded-xl p-3 space-y-2">
          <div className="flex gap-1 bg-gray-200 rounded-lg p-0.5 text-xs font-medium">
            {(["direct", "email"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setInviteMode(m)}
                className={`flex-1 py-1 rounded-md transition-colors ${inviteMode === m ? "bg-white text-gray-800 shadow-sm" : "text-gray-500"}`}
              >
                {m === "direct" ? "Criar agora" : "Enviar link"}
              </button>
            ))}
          </div>
          <p className="text-xs font-semibold text-gray-600">
            {inviteMode === "direct" ? "Criar conta com senha temporária" : "Enviar convite por e-mail"}</p>
          <input
            type="email"
            placeholder="email@empresa.com"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          {inviteMode === "direct" && (
            <input
              type="text"
              placeholder="Nome (opcional)"
              value={inviteName}
              onChange={(e) => setInviteName(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          )}
          <select
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value as TenantRole)}
            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>{ROLE_LABELS[r]}</option>
            ))}
          </select>
          {inviteMut.error && (
            <p className="text-xs text-red-600">
              {(inviteMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao convidar"}
            </p>
          )}
          <div className="flex gap-2">
            <button
              onClick={() => inviteMut.mutate()}
              disabled={!inviteEmail || inviteMut.isPending}
              className="flex-1 bg-brand-600 text-white text-xs font-medium py-1.5 rounded-lg hover:bg-brand-700 disabled:opacity-50 transition-colors"
            >
              {inviteMut.isPending ? "Enviando..." : inviteMode === "direct" ? "Criar conta" : "Enviar link"}
            </button>
            <button
              onClick={() => setShowInvite(false)}
              className="flex-1 border border-gray-300 text-gray-600 text-xs font-medium py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-gray-400 text-center py-4">Carregando...</p>
      ) : members.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">Nenhum membro encontrado.</p>
      ) : (
        <div className="space-y-1 overflow-y-auto flex-1">
          {members.map((m: TenantMember) => (
            <div
              key={m.user_id}
              className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 group"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{m.name}</p>
                <p className="text-xs text-gray-500 truncate">{m.email}</p>
              </div>
              <div className="flex items-center gap-2 ml-2 shrink-0">
                {editingUserId === m.user_id ? (
                  <>
                    <select
                      value={editRole}
                      onChange={(e) => setEditRole(e.target.value as TenantRole)}
                      className="border border-gray-300 rounded px-1.5 py-0.5 text-xs"
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                      ))}
                    </select>
                    <button
                      onClick={() => updateRoleMut.mutate({ userId: m.user_id, role: editRole })}
                      className="text-green-600 hover:text-green-800"
                    >
                      <Check size={14} />
                    </button>
                    <button onClick={() => setEditingUserId(null)} className="text-gray-400 hover:text-gray-600">
                      <X size={14} />
                    </button>
                  </>
                ) : (
                  <>
                    <RoleBadge role={m.role} />
                    <button
                      onClick={() => { setPermUserId(m.user_id); setPermUserName(m.name); }}
                      className="text-gray-400 hover:text-brand-600 opacity-0 group-hover:opacity-100 transition-opacity"
                      title="Matriz de permissões"
                    >
                      <ShieldCheck size={13} />
                    </button>
                    <button
                      onClick={() => { setEditingUserId(m.user_id); setEditRole(m.role); }}
                      className="text-gray-400 hover:text-brand-600 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <Edit2 size={13} />
                    </button>
                    {m.user_id !== currentUserId && (
                      <button
                        onClick={() => { if (confirm(`Remover ${m.name}?`)) removeMut.mutate(m.user_id); }}
                        className="text-gray-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Super admin view ─────────────────────────────────────────────────────────

function SuperAdminView() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [selectedTenantId, setSelectedTenantId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createSlug, setCreateSlug] = useState("");
  const [editingTenantId, setEditingTenantId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");

  const { data: tenants = [], isLoading } = useQuery({
    queryKey: ["tenants"],
    queryFn: tenantsApi.list,
  });

  const createMut = useMutation({
    mutationFn: () => tenantsApi.create({ name: createName, slug: createSlug }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenants"] });
      setShowCreate(false);
      setCreateName("");
      setCreateSlug("");
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; is_active?: boolean } }) =>
      tenantsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenants"] });
      setEditingTenantId(null);
    },
  });

  const selectedTenant = tenants.find((t) => t.id === selectedTenantId);

  return (
    <main className="flex-1 ml-64 flex flex-col h-screen">
      <TopBar title="Tenants" />
      <div className="flex flex-1 overflow-hidden">
        {/* Left: tenant list */}
        <div className="w-80 border-r border-gray-200 flex flex-col overflow-hidden bg-white">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <span className="text-sm font-semibold text-gray-700">Todos os tenants</span>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-800 transition-colors"
            >
              <Plus size={13} />
              Novo
            </button>
          </div>

          {showCreate && (
            <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 space-y-2">
              <input
                type="text"
                placeholder="Nome do tenant"
                value={createName}
                onChange={(e) => {
                  setCreateName(e.target.value);
                  setCreateSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""));
                }}
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <input
                type="text"
                placeholder="slug (ex: acme-corp)"
                value={createSlug}
                onChange={(e) => setCreateSlug(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              {createMut.error && (
                <p className="text-xs text-red-600">
                  {(createMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao criar"}
                </p>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => createMut.mutate()}
                  disabled={!createName || !createSlug || createMut.isPending}
                  className="flex-1 bg-brand-600 text-white text-xs font-medium py-1.5 rounded-lg hover:bg-brand-700 disabled:opacity-50 transition-colors"
                >
                  {createMut.isPending ? "Criando..." : "Criar"}
                </button>
                <button
                  onClick={() => setShowCreate(false)}
                  className="flex-1 border border-gray-300 text-gray-600 text-xs font-medium py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}

          <div className="flex-1 overflow-y-auto">
            {isLoading ? (
              <p className="text-sm text-gray-400 text-center py-6">Carregando...</p>
            ) : (
              tenants.map((t: TenantRead) => (
                <div
                  key={t.id}
                  onClick={() => setSelectedTenantId(t.id === selectedTenantId ? null : t.id)}
                  className={`flex items-center gap-3 px-4 py-3 cursor-pointer border-b border-gray-50 group transition-colors ${
                    selectedTenantId === t.id ? "bg-brand-50" : "hover:bg-gray-50"
                  }`}
                >
                  <Building2 size={15} className={t.is_active ? "text-brand-500" : "text-gray-300"} />
                  <div className="flex-1 min-w-0">
                    {editingTenantId === t.id ? (
                      <div
                        className="flex items-center gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          autoFocus
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          className="flex-1 border border-gray-300 rounded px-2 py-0.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand-500"
                        />
                        <button
                          onClick={() => updateMut.mutate({ id: t.id, data: { name: editName } })}
                          className="text-green-600 hover:text-green-800"
                        >
                          <Check size={13} />
                        </button>
                        <button
                          onClick={() => setEditingTenantId(null)}
                          className="text-gray-400 hover:text-gray-600"
                        >
                          <X size={13} />
                        </button>
                      </div>
                    ) : (
                      <>
                        <p className={`text-sm font-medium truncate ${t.is_active ? "text-gray-900" : "text-gray-400 line-through"}`}>
                          {t.name}
                        </p>
                        <p className="text-xs text-gray-400 font-mono">{t.slug}</p>
                      </>
                    )}
                  </div>
                  {editingTenantId !== t.id && (
                    <div
                      className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={() => { setEditingTenantId(t.id); setEditName(t.name); }}
                        className="text-gray-400 hover:text-brand-600 p-0.5"
                        title="Renomear"
                      >
                        <Edit2 size={12} />
                      </button>
                      <button
                        onClick={() => updateMut.mutate({ id: t.id, data: { is_active: !t.is_active } })}
                        className={`p-0.5 ${t.is_active ? "text-gray-400 hover:text-amber-600" : "text-gray-300 hover:text-green-600"}`}
                        title={t.is_active ? "Desativar" : "Ativar"}
                      >
                        {t.is_active ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                      </button>
                    </div>
                  )}
                  {selectedTenantId === t.id && editingTenantId !== t.id && (
                    <ChevronRight size={13} className="text-brand-500 shrink-0" />
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right: members panel */}
        <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
          {selectedTenant ? (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-5 h-full">
              <MembersPanel
                tenantId={selectedTenant.id}
                tenantName={selectedTenant.name}
                currentUserId={user?.id ?? ""}
              />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Building2 size={40} className="text-gray-200 mb-3" />
              <p className="text-sm text-gray-400">Selecione um tenant para gerenciar seus membros</p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

// ── Tenant admin view ────────────────────────────────────────────────────────

function TenantAdminView() {
  const { user, tenant } = useAuth();

  if (!tenant) {
    return (
      <main className="flex-1 ml-64">
        <TopBar title="Tenants" />
        <div className="p-6 text-sm text-gray-500">Nenhum tenant ativo.</div>
      </main>
    );
  }

  return (
    <main className="flex-1 ml-64 flex flex-col h-screen">
      <TopBar title="Gestão de Membros" />
      <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
        <div className="max-w-xl bg-white rounded-2xl shadow-sm border border-gray-200 p-5">
          <MembersPanel
            tenantId={tenant.id}
            tenantName={tenant.name}
            currentUserId={user?.id ?? ""}
          />
        </div>
      </div>
    </main>
  );
}

// ── Page entry point ─────────────────────────────────────────────────────────

export function Tenants() {
  const { user, tenant: activeTenant, tenantRole } = useAuth();
  const isSuperAdmin = user?.is_super_admin ?? false;

  if (!isSuperAdmin && tenantRole !== "admin") {
    return (
      <main className="flex-1 ml-64">
        <TopBar title="Tenants" />
        <div className="flex items-center justify-center h-64">
          <p className="text-sm text-gray-400">Acesso restrito a administradores.</p>
        </div>
      </main>
    );
  }

  if (isSuperAdmin) return <SuperAdminView />;
  return <TenantAdminView />;
}
