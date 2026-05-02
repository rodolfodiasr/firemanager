import { Fragment, useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Building2, Plus, UserPlus, Trash2, Edit2, Check, X,
  KeyRound, ToggleLeft, ToggleRight, Users, ShieldCheck,
  Globe, ChevronDown, ChevronUp, Loader2, CheckCircle2, XCircle,
} from "lucide-react";
import toast from "react-hot-toast";
import { useForm } from "react-hook-form";
import { PageWrapper } from "../components/layout/PageWrapper";
import { useAuth } from "../hooks/useAuth";
import { tenantsApi } from "../api/tenants";
import { inviteApi } from "../api/invite";
import { permissionsApi, type DeviceCategory, type FunctionalModule } from "../api/permissions";
import { integrationsApi } from "../api/integrations";
import { auditApi } from "../api/audit";
import { AUDIT_INTENTS, type AuditPolicy, type UserForPolicy } from "../types/audit";
import type { Integration, IntegrationType } from "../types/integration";
import type { TenantMember, TenantRead, TenantRole } from "../types/tenant";

// ── Role constants ────────────────────────────────────────────────────────────

const ROLES: TenantRole[] = ["admin", "analyst_n2", "analyst_n1", "readonly"];
const ROLE_LABELS: Record<TenantRole, string> = {
  admin:      "Admin",
  analyst_n2: "Analista N2",
  analyst_n1: "Analista N1",
  readonly:   "Leitor",
  analyst:    "Analista (legado)",
};
const ROLE_COLORS: Record<TenantRole, string> = {
  admin:      "bg-brand-100 text-brand-700",
  analyst_n2: "bg-blue-100 text-blue-700",
  analyst_n1: "bg-cyan-100 text-cyan-700",
  readonly:   "bg-gray-100 text-gray-600",
  analyst:    "bg-blue-100 text-blue-600",
};

function RoleBadge({ role }: { role: TenantRole }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${ROLE_COLORS[role]}`}>
      {ROLE_LABELS[role]}
    </span>
  );
}

// ── Permission Matrix Drawer ──────────────────────────────────────────────────

const DEVICE_CATS: { key: DeviceCategory; label: string }[] = [
  { key: "firewall",   label: "Firewall" },
  { key: "switch",     label: "Switch / Roteador" },
  { key: "server",     label: "Servidor" },
  { key: "hypervisor", label: "Hypervisor" },
];
const FUNC_MODULES: { key: FunctionalModule; label: string }[] = [
  { key: "compliance",      label: "Compliance" },
  { key: "remediation",     label: "Remediação" },
  { key: "server_analysis", label: "Análise de Servidores" },
  { key: "bulk_jobs",       label: "Jobs em Lote" },
];
const PERM_ROLES: { value: TenantRole | ""; label: string }[] = [
  { value: "",           label: "— (herdar)" },
  { value: "admin",      label: "Admin" },
  { value: "analyst_n2", label: "Analista N2" },
  { value: "analyst_n1", label: "Analista N1" },
  { value: "readonly",   label: "Leitor" },
];

function PermissionMatrixDrawer({
  tenantId, userId, userName, onClose,
}: {
  tenantId: string; userId: string; userName: string; onClose: () => void;
}) {
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

  const getCatOverride = (cat: DeviceCategory): TenantRole | "" =>
    profile?.category_roles.find((cr) => cr.category === cat)?.role ?? "";
  const getModOverride = (mod: FunctionalModule): TenantRole | "" =>
    profile?.module_roles.find((mr) => mr.module === mod)?.role ?? "";

  const handleCatChange = (cat: DeviceCategory, val: TenantRole | "") =>
    val === "" ? deleteCat.mutate(cat) : upsertCat.mutate({ cat, role: val });
  const handleModChange = (mod: FunctionalModule, val: TenantRole | "") =>
    val === "" ? deleteMod.mutate(mod) : upsertMod.mutate({ mod, role: val });

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-white shadow-2xl flex flex-col h-full overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 shrink-0">
          <div className="flex items-center gap-2">
            <ShieldCheck size={18} className="text-brand-600" />
            <h2 className="text-base font-semibold text-gray-900">Permissões — {userName}</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>

        {isLoading ? (
          <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">Carregando...</div>
        ) : (
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
            <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3 text-xs text-blue-800 leading-relaxed">
              As permissões são resolvidas em cascata:{" "}
              <span className="font-semibold">override de módulo/categoria &gt; perfil global do tenant</span>.
              Se nenhum override estiver definido, o usuário herda o perfil global.
            </div>

            {profile && (
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span>Perfil base:</span>
                <span className="font-semibold text-gray-800 bg-gray-100 px-2 py-0.5 rounded-full">
                  {ROLE_LABELS[profile.tenant_role] ?? profile.tenant_role}
                </span>
                <span className="text-gray-400">— aplicado onde não há override</span>
              </div>
            )}

            <div>
              <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-0.5">Categorias de Dispositivo</p>
              <p className="text-xs text-gray-400 mb-3">
                Controla quais ações o usuário pode executar por tipo de equipamento. Deixe em "— herdar" para usar o perfil base.
              </p>
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
                            {PERM_ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                          </select>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div>
              <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-0.5">Módulos Funcionais</p>
              <p className="text-xs text-gray-400 mb-3">
                Controla o acesso por área de trabalho, independente do tipo de dispositivo.
              </p>
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
                            {PERM_ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                          </select>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="border-t border-gray-100 pt-4">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">O que cada perfil pode fazer</p>
              <div className="space-y-2">
                {[
                  { role: "Admin",       color: "bg-brand-100 text-brand-700",  desc: "Executa diretamente, sem aprovação. Pode aprovar operações de outros." },
                  { role: "Analista N2", color: "bg-blue-100 text-blue-700",    desc: "Executa operações de baixo risco diretamente. Críticas vão para a fila conforme a política." },
                  { role: "Analista N1", color: "bg-cyan-100 text-cyan-700",    desc: "Todas as operações vão para fila de revisão N2. Nunca executa diretamente." },
                  { role: "Leitor",      color: "bg-gray-100 text-gray-600",    desc: "Apenas visualização. Sem permissão de execução, remediação ou geração de planos." },
                  { role: "— (herdar)", color: "bg-gray-50 text-gray-500 border border-gray-200", desc: "Usa o perfil base do tenant definido acima." },
                ].map(({ role, color, desc }) => (
                  <div key={role} className="flex items-start gap-2">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ${color}`}>{role}</span>
                    <p className="text-xs text-gray-500 leading-relaxed">{desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Members Panel ─────────────────────────────────────────────────────────────

function MembersPanel({ tenantId, tenantName, currentUserId }: {
  tenantId: string; tenantName: string; currentUserId: string;
}) {
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
        setInviteEmail(""); setInviteName(""); setInviteRole("analyst_n2");
      }
    },
  });

  const updateRoleMut = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: TenantRole }) =>
      tenantsApi.updateMemberRole(tenantId, userId, role),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["members", tenantId] }); setEditingUserId(null); },
  });

  const removeMut = useMutation({
    mutationFn: (userId: string) => tenantsApi.removeMember(tenantId, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["members", tenantId] }),
  });

  return (
    <div className="flex flex-col">
      {permUserId && (
        <PermissionMatrixDrawer
          tenantId={tenantId} userId={permUserId} userName={permUserName}
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
          <button onClick={() => setTempPassword(null)} className="text-amber-600 hover:text-amber-800 mt-1 underline">Fechar</button>
        </div>
      )}

      {showInvite && emailSent && (
        <div className="mb-3 bg-green-50 border border-green-200 rounded-xl p-3 text-xs text-green-800">
          <p className="font-semibold mb-1">Convite enviado!</p>
          <p>Um e-mail foi enviado para <strong>{inviteEmail}</strong> com o link de acesso.</p>
          <button
            onClick={() => { setEmailSent(false); setShowInvite(false); setInviteEmail(""); setInviteRole("analyst_n2"); }}
            className="mt-2 text-green-600 underline"
          >Fechar</button>
        </div>
      )}

      {showInvite && !emailSent && (
        <div className="mb-4 bg-gray-50 border border-gray-200 rounded-xl p-3 space-y-2">
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
            {inviteMode === "direct" ? "Criar conta com senha temporária" : "Enviar convite por e-mail"}
          </p>
          <input
            type="email" placeholder="email@empresa.com" value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          {inviteMode === "direct" && (
            <input
              type="text" placeholder="Nome (opcional)" value={inviteName}
              onChange={(e) => setInviteName(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          )}
          <select
            value={inviteRole} onChange={(e) => setInviteRole(e.target.value as TenantRole)}
            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
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
        <div className="space-y-1">
          {members.map((m: TenantMember) => (
            <div key={m.user_id} className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 group">
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{m.name}</p>
                <p className="text-xs text-gray-500 truncate">{m.email}</p>
              </div>
              <div className="flex items-center gap-2 ml-2 shrink-0">
                {editingUserId === m.user_id ? (
                  <>
                    <select
                      value={editRole} onChange={(e) => setEditRole(e.target.value as TenantRole)}
                      className="border border-gray-300 rounded px-1.5 py-0.5 text-xs"
                    >
                      {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                    </select>
                    <button onClick={() => updateRoleMut.mutate({ userId: m.user_id, role: editRole })} className="text-green-600 hover:text-green-800">
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

// ── Tenants Tab (super admin only) ────────────────────────────────────────────

function TenantsTab() {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createSlug, setCreateSlug] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");

  const { data: tenants = [], isLoading } = useQuery({
    queryKey: ["tenants"],
    queryFn: tenantsApi.list,
  });

  const createMut = useMutation({
    mutationFn: () => tenantsApi.create({ name: createName, slug: createSlug }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenants"] });
      setShowCreate(false); setCreateName(""); setCreateSlug("");
      toast.success("Tenant criado.");
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Erro ao criar tenant.");
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; is_active?: boolean } }) =>
      tenantsApi.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["tenants"] }); setEditingId(null); },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <p className="text-sm text-gray-500">
          Tenants cadastrados na plataforma. O tenant{" "}
          <code className="bg-gray-100 px-1 rounded text-xs font-mono">default</code>{" "}
          não pode ser removido.
        </p>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 text-sm font-medium bg-brand-600 text-white px-3 py-1.5 rounded-lg hover:bg-brand-700 transition-colors"
        >
          <Plus size={14} />
          Novo Tenant
        </button>
      </div>

      {showCreate && (
        <div className="mb-5 bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3 max-w-md">
          <p className="text-sm font-semibold text-gray-700">Novo Tenant</p>
          <input
            type="text" placeholder="Nome do tenant" value={createName}
            onChange={(e) => {
              setCreateName(e.target.value);
              setCreateSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""));
            }}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <input
            type="text" placeholder="slug (ex: acme-corp)" value={createSlug}
            onChange={(e) => setCreateSlug(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
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
              className="flex-1 bg-brand-600 text-white text-sm font-medium py-1.5 rounded-lg hover:bg-brand-700 disabled:opacity-50"
            >
              {createMut.isPending ? "Criando..." : "Criar"}
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="flex-1 border border-gray-300 text-gray-600 text-sm font-medium py-1.5 rounded-lg hover:bg-gray-50"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-gray-400">Carregando...</p>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3">Nome</th>
                <th className="text-left px-4 py-3">Slug</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="px-4 py-3 w-20" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {tenants.map((t: TenantRead) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    {editingId === t.id ? (
                      <div className="flex items-center gap-2">
                        <input
                          autoFocus value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-brand-500"
                        />
                        <button onClick={() => updateMut.mutate({ id: t.id, data: { name: editName } })} className="text-green-600 hover:text-green-800">
                          <Check size={14} />
                        </button>
                        <button onClick={() => setEditingId(null)} className="text-gray-400 hover:text-gray-600">
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <span className="font-medium text-gray-900">{t.name}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{t.slug}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      t.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                    }`}>
                      {t.is_active ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 justify-end">
                      {editingId !== t.id && (
                        <button
                          onClick={() => { setEditingId(t.id); setEditName(t.name); }}
                          className="text-gray-400 hover:text-brand-600 transition-colors"
                          title="Renomear"
                        >
                          <Edit2 size={13} />
                        </button>
                      )}
                      <button
                        onClick={() => updateMut.mutate({ id: t.id, data: { is_active: !t.is_active } })}
                        className={`transition-colors ${t.is_active ? "text-gray-400 hover:text-amber-600" : "text-gray-300 hover:text-green-600"}`}
                        title={t.is_active ? "Desativar" : "Ativar"}
                      >
                        {t.is_active ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                      </button>
                    </div>
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

// ── Equipe Tab ────────────────────────────────────────────────────────────────

function EquipeTab() {
  const { user, tenant } = useAuth();
  const isSuperAdmin = user?.is_super_admin ?? false;
  const [selectedTenantId, setSelectedTenantId] = useState<string>(
    isSuperAdmin ? "" : (tenant?.id ?? "")
  );

  const { data: tenants = [] } = useQuery({
    queryKey: ["tenants"],
    queryFn: tenantsApi.list,
    enabled: isSuperAdmin,
  });

  const activeTenantId = isSuperAdmin ? selectedTenantId : (tenant?.id ?? "");
  const activeTenantName = isSuperAdmin
    ? (tenants.find((t: TenantRead) => t.id === selectedTenantId)?.name ?? "")
    : (tenant?.name ?? "");

  return (
    <div>
      {isSuperAdmin && (
        <div className="flex items-center gap-3 mb-6">
          <label className="text-sm font-medium text-gray-700 shrink-0">Tenant:</label>
          <select
            value={selectedTenantId}
            onChange={(e) => setSelectedTenantId(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 min-w-[240px]"
          >
            <option value="">Selecione um tenant...</option>
            {tenants.map((t: TenantRead) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
      )}

      {activeTenantId ? (
        <MembersPanel
          tenantId={activeTenantId}
          tenantName={activeTenantName}
          currentUserId={user?.id ?? ""}
        />
      ) : (
        <div className="text-center py-14 text-gray-400">
          <Users size={36} className="mx-auto mb-3 text-gray-200" />
          <p className="text-sm">Selecione um tenant para gerenciar a equipe.</p>
        </div>
      )}
    </div>
  );
}

// ── Política Tab ──────────────────────────────────────────────────────────────

const POLICY_ROLES = ["operator", "viewer"] as const;
const POLICY_ROLE_LABELS: Record<string, string> = {
  operator: "Operador (N1)",
  viewer:   "Visualizador",
};
const GROUPS = Array.from(new Set(AUDIT_INTENTS.map((i) => i.group)));
const DEFAULT_APPROVAL: Record<string, boolean> = Object.fromEntries(
  AUDIT_INTENTS.map((i) => [i.key, i.defaultApproval])
);

function policyValue(policies: AuditPolicy[], scopeType: string, scopeId: string, intent: string): boolean | null {
  const p = policies.find((p) => p.scope_type === scopeType && p.scope_id === scopeId && p.intent === intent);
  return p !== undefined ? p.requires_approval : null;
}

function effectiveValue(policies: AuditPolicy[], scopeType: string, scopeId: string, intent: string): boolean {
  const v = policyValue(policies, scopeType, scopeId, intent);
  return v !== null ? v : (DEFAULT_APPROVAL[intent] ?? false);
}

function PoliticaTab() {
  const qc = useQueryClient();
  const { data: policies = [] } = useQuery({ queryKey: ["audit-policies"], queryFn: auditApi.getPolicies });
  const { data: users = [] }    = useQuery({ queryKey: ["audit-users"],    queryFn: auditApi.getUsers });

  const [view, setView] = useState<"roles" | "users">("roles");
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);

  const upsertMutation = useMutation({
    mutationFn: auditApi.upsertPolicy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["audit-policies"] }),
    onError: () => toast.error("Erro ao salvar política."),
  });
  const deleteMutation = useMutation({
    mutationFn: ({ scopeType, scopeId, intent }: { scopeType: string; scopeId: string; intent: string }) =>
      auditApi.deletePolicy(scopeType, scopeId, intent),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["audit-policies"] }),
    onError: () => toast.error("Erro ao remover override."),
  });

  const selectedUser = users.find((u: UserForPolicy) => u.id === selectedUserId);

  return (
    <div>
      <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3 text-xs text-blue-800 leading-relaxed mb-5">
        Define quais tipos de operação requerem aprovação de um{" "}
        <span className="font-semibold">Analista N2</span> antes de executar.
        Admins sempre executam diretamente. Analistas N1 sempre entram na fila, independente desta política.
        Overrides individuais têm prioridade sobre o perfil.
      </div>

      <div className="flex gap-1 mb-5 bg-gray-100 rounded-lg p-1 w-fit">
        {(["roles", "users"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              view === v ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {v === "roles" ? "Por Perfil" : "Por Usuário"}
          </button>
        ))}
      </div>

      {view === "roles" && (
        <>
          <p className="text-xs text-gray-500 mb-4">
            Checkboxes marcados = a intenção exige aprovação antes de executar para aquele perfil.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase w-1/2">Intenção</th>
                  {POLICY_ROLES.map((role) => (
                    <th key={role} className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase text-center">
                      {POLICY_ROLE_LABELS[role]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {GROUPS.map((group) => (
                  <Fragment key={group}>
                    <tr className="bg-gray-50/70">
                      <td colSpan={POLICY_ROLES.length + 1} className="px-4 py-1.5 text-xs font-semibold text-gray-600 uppercase tracking-wide">
                        {group}
                      </td>
                    </tr>
                    {AUDIT_INTENTS.filter((i) => i.group === group).map((intent) => (
                      <tr key={intent.key} className="border-t border-gray-100 hover:bg-gray-50">
                        <td className="px-4 py-2.5 text-gray-700">{intent.label}</td>
                        {POLICY_ROLES.map((role) => {
                          const override = policyValue(policies, "role", role, intent.key);
                          const effective = override !== null ? override : (DEFAULT_APPROVAL[intent.key] ?? false);
                          return (
                            <td key={role} className="px-4 py-2.5 text-center">
                              <div className="flex flex-col items-center gap-0.5">
                                <input
                                  type="checkbox" checked={effective}
                                  onChange={(e) => upsertMutation.mutate({
                                    scope_type: "role", scope_id: role,
                                    intent: intent.key, requires_approval: e.target.checked,
                                  })}
                                  disabled={upsertMutation.isPending}
                                  className="h-4 w-4 rounded border-gray-300 text-brand-600 cursor-pointer"
                                />
                                {override !== null && (
                                  <span className="text-[10px] text-brand-600 font-medium">override</span>
                                )}
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {view === "users" && (
        <>
          <div className="flex items-center gap-3 mb-5">
            <label className="text-sm font-medium text-gray-700 shrink-0">Usuário:</label>
            <select
              value={selectedUserId ?? ""}
              onChange={(e) => setSelectedUserId(e.target.value || null)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 min-w-[280px]"
            >
              <option value="">Selecione um usuário...</option>
              {users
                .filter((u: UserForPolicy) => u.role !== "admin")
                .map((u: UserForPolicy) => (
                  <option key={u.id} value={u.id}>{u.name} ({u.email}) — {u.role}</option>
                ))}
            </select>
          </div>

          {!selectedUserId ? (
            <p className="text-sm text-gray-400 text-center py-10">
              Selecione um usuário para ver e configurar seus overrides de política.
            </p>
          ) : (
            <>
              <p className="text-xs text-gray-500 mb-4">
                Overrides individuais têm prioridade sobre o perfil "{selectedUser?.role}".
                Remover um override faz voltar à política do perfil.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Intenção</th>
                      <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase text-center">Requer Aprovação</th>
                      <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase text-center">Override</th>
                    </tr>
                  </thead>
                  <tbody>
                    {GROUPS.map((group) => (
                      <Fragment key={group}>
                        <tr className="bg-gray-50/70">
                          <td colSpan={3} className="px-4 py-1.5 text-xs font-semibold text-gray-600 uppercase tracking-wide">
                            {group}
                          </td>
                        </tr>
                        {AUDIT_INTENTS.filter((i) => i.group === group).map((intent) => {
                          const userOverride  = policyValue(policies, "user", selectedUserId, intent.key);
                          const roleEffective = effectiveValue(policies, "role", selectedUser?.role ?? "", intent.key);
                          const effective     = userOverride !== null ? userOverride : roleEffective;
                          return (
                            <tr key={intent.key} className="border-t border-gray-100 hover:bg-gray-50">
                              <td className="px-4 py-2.5 text-gray-700">{intent.label}</td>
                              <td className="px-4 py-2.5 text-center">
                                <input
                                  type="checkbox" checked={effective}
                                  onChange={(e) => upsertMutation.mutate({
                                    scope_type: "user", scope_id: selectedUserId,
                                    intent: intent.key, requires_approval: e.target.checked,
                                  })}
                                  disabled={upsertMutation.isPending || deleteMutation.isPending}
                                  className="h-4 w-4 rounded border-gray-300 text-brand-600 cursor-pointer"
                                />
                              </td>
                              <td className="px-4 py-2.5 text-center">
                                {userOverride !== null ? (
                                  <button
                                    onClick={() => deleteMutation.mutate({ scopeType: "user", scopeId: selectedUserId, intent: intent.key })}
                                    disabled={deleteMutation.isPending}
                                    className="text-xs text-red-500 hover:text-red-700 underline"
                                  >Remover</button>
                                ) : (
                                  <span className="text-xs text-gray-400">—</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

// ── Integrações Tab ───────────────────────────────────────────────────────────

const INTEGRATION_META: Record<IntegrationType, {
  label: string; description: string; color: string;
  fields: { key: string; label: string; type?: string; placeholder?: string; defaultValue?: string; options?: { value: string; label: string }[] }[];
}> = {
  shodan: {
    label: "Shodan", description: "Varredura de ativos expostos na internet e CVEs por IP.",
    color: "bg-red-100 text-red-700",
    fields: [{ key: "api_key", label: "API Key", type: "password", placeholder: "Sua API key do Shodan" }],
  },
  wazuh: {
    label: "Wazuh", description: "SIEM open-source — correlação de eventos e alertas de segurança.",
    color: "bg-blue-100 text-blue-700",
    fields: [
      { key: "url",      label: "URL",    placeholder: "https://wazuh.empresa.com:55000" },
      { key: "username", label: "Usuário", placeholder: "wazuh-api" },
      { key: "password", label: "Senha",  type: "password", placeholder: "••••••••" },
      { key: "version",  label: "Versão", type: "select", defaultValue: "4", options: [{ value: "4", label: "Wazuh 4.x" }, { value: "5", label: "Wazuh 5.x" }] },
      { key: "verify_ssl", label: "Verificar SSL", type: "checkbox" },
    ],
  },
  openvas: {
    label: "OpenVAS / GVM", description: "Scanner de vulnerabilidades open-source (Greenbone).",
    color: "bg-green-100 text-green-700",
    fields: [
      { key: "host",     label: "Host",      placeholder: "192.168.1.100" },
      { key: "port",     label: "Porta GMP", placeholder: "9390", defaultValue: "9390" },
      { key: "username", label: "Usuário",   placeholder: "admin" },
      { key: "password", label: "Senha",     type: "password", placeholder: "••••••••" },
    ],
  },
  nmap: {
    label: "Nmap", description: "Scanner de portas e serviços para descoberta de rede.",
    color: "bg-purple-100 text-purple-700",
    fields: [
      { key: "binary_path",  label: "Caminho do binário", placeholder: "/usr/bin/nmap",  defaultValue: "/usr/bin/nmap" },
      { key: "default_args", label: "Args padrão",        placeholder: "-sS -T4",        defaultValue: "-sS -T4" },
    ],
  },
  zabbix: {
    label: "Zabbix", description: "Monitoramento de infraestrutura — hosts, métricas, alertas e triggers.",
    color: "bg-orange-100 text-orange-700",
    fields: [
      { key: "url",     label: "URL",       placeholder: "https://zabbix.empresa.com" },
      { key: "token",   label: "API Token", type: "password", placeholder: "Token gerado no Zabbix" },
      { key: "version", label: "Versão",    type: "select", defaultValue: "7", options: [{ value: "6", label: "Zabbix 6.x" }, { value: "7", label: "Zabbix 7.x (7.2.5+)" }] },
      { key: "verify_ssl", label: "Verificar SSL", type: "checkbox" },
    ],
  },
  bookstack: {
    label: "BookStack", description: "Base de conhecimento — documentação via RAG.",
    color: "bg-sky-100 text-sky-700",
    fields: [
      { key: "base_url",         label: "URL do BookStack",         placeholder: "https://bookstack.suaempresa.com" },
      { key: "token_id",         label: "Token ID",                 placeholder: "ID do token de API" },
      { key: "token_secret",     label: "Token Secret",             type: "password", placeholder: "Secret do token de API" },
      { key: "book_id",          label: "ID do Livro (book_id)",    placeholder: "1" },
      { key: "chapter_id",       label: "ID do Chapter (opcional)", placeholder: "Deixe vazio para indexar o livro inteiro" },
      { key: "snapshot_enabled", label: "Snapshot automático",      type: "checkbox" },
      { key: "snapshot_hour",    label: "Horário do snapshot (UTC)", type: "select", defaultValue: "2",
        options: Array.from({ length: 24 }, (_, i) => ({ value: String(i), label: `${String(i).padStart(2, "0")}:00 UTC` })) },
    ],
  },
};

function IntegrationCard({ type, existing, tenantId, isSuperAdmin }: {
  type: IntegrationType; existing: Integration | undefined; tenantId: string | null; isSuperAdmin: boolean;
}) {
  const qc = useQueryClient();
  const meta = INTEGRATION_META[type];
  const [open, setOpen] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; latency_ms?: number } | null>(null);
  const [testing, setTesting] = useState(false);

  const { register, handleSubmit, reset, formState: { isSubmitting } } = useForm({
    defaultValues: meta.fields.reduce((acc, f) => ({ ...acc, [f.key]: f.defaultValue ?? "" }), {} as Record<string, string>),
  });

  useEffect(() => {
    if (!open) return;
    const preview = existing?.config_preview ?? {};
    const values: Record<string, string> = {};
    meta.fields.forEach((f) => {
      const v = preview[f.key];
      if (v === undefined || v === "__masked__") values[f.key] = f.defaultValue ?? "";
      else if (f.type === "checkbox") values[f.key] = v ? "true" : "false";
      else values[f.key] = String(v);
    });
    reset(values);
  }, [open]);

  const saveMut = useMutation({
    mutationFn: async (formData: Record<string, string>) => {
      const config: Record<string, unknown> = {};
      meta.fields.forEach((f) => {
        if (f.type === "checkbox")     config[f.key] = formData[f.key] === "true" || formData[f.key] === "on";
        else if (f.key === "port")     config[f.key] = parseInt(formData[f.key]) || 9390;
        else if (f.key === "book_id")  config[f.key] = parseInt(formData[f.key]) || 1;
        else if (f.key === "chapter_id") { const v = parseInt(formData[f.key]); if (v) config[f.key] = v; }
        else if (f.key === "snapshot_hour") config[f.key] = parseInt(formData[f.key]) || 2;
        else config[f.key] = formData[f.key];
      });
      if (existing) return integrationsApi.update(existing.id, { config });
      return integrationsApi.create({ type, name: meta.label, config, tenant_id: isSuperAdmin ? null : tenantId });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["integrations"] }); setOpen(false); },
  });

  const deleteMut = useMutation({
    mutationFn: () => integrationsApi.remove(existing!.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["integrations"] }),
  });

  const handleTest = async () => {
    if (!existing) return;
    setTesting(true); setTestResult(null);
    try {
      setTestResult(await integrationsApi.test(existing.id));
    } catch {
      setTestResult({ success: false, message: "Erro ao testar integração" });
    } finally {
      setTesting(false);
    }
  };

  const scopeBadge = existing
    ? existing.scope === "global"
      ? <span className="flex items-center gap-1 text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full"><Globe size={10} />Global</span>
      : <span className="flex items-center gap-1 text-xs bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full"><Building2 size={10} />Tenant</span>
    : null;

  return (
    <div className={`bg-white rounded-xl border ${existing?.is_active ? "border-gray-200" : "border-gray-100 opacity-60"} p-5 flex flex-col gap-3`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${meta.color}`}>{meta.label}</span>
            {scopeBadge}
          </div>
          <p className="text-xs text-gray-500 mt-1">{meta.description}</p>
        </div>
        {existing ? <CheckCircle2 size={18} className="text-green-500 shrink-0" /> : <XCircle size={18} className="text-gray-300 shrink-0" />}
      </div>

      {testResult && (
        <div className={`text-xs rounded-lg px-3 py-2 ${testResult.success ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>
          {testResult.success ? "✓" : "✗"} {testResult.message}
          {testResult.latency_ms && <span className="ml-2 text-gray-400">{testResult.latency_ms.toFixed(0)}ms</span>}
        </div>
      )}

      {open && (
        <form onSubmit={handleSubmit((d) => saveMut.mutate(d as Record<string, string>))} className="space-y-3 pt-2 border-t border-gray-100">
          {meta.fields.map((f) =>
            f.type === "checkbox" ? (
              <label key={f.key} className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" {...register(f.key)} className="rounded" />
                {f.label}
              </label>
            ) : f.type === "select" ? (
              <div key={f.key}>
                <label className="block text-xs font-medium text-gray-600 mb-1">{f.label}</label>
                <select {...register(f.key)} className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                  {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            ) : (
              <div key={f.key}>
                <label className="block text-xs font-medium text-gray-600 mb-1">{f.label}</label>
                <input
                  type={f.type ?? "text"} {...register(f.key)} placeholder={f.placeholder}
                  className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            )
          )}
          {saveMut.error && (
            <p className="text-xs text-red-600">
              {(saveMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao salvar"}
            </p>
          )}
          <div className="flex gap-2">
            <button type="submit" disabled={isSubmitting || saveMut.isPending}
              className="flex-1 bg-brand-600 text-white text-xs font-medium py-1.5 rounded-lg hover:bg-brand-700 disabled:opacity-50">
              {saveMut.isPending ? "Salvando..." : "Salvar"}
            </button>
            <button type="button" onClick={() => setOpen(false)}
              className="flex-1 border border-gray-300 text-gray-600 text-xs font-medium py-1.5 rounded-lg hover:bg-gray-50">
              Cancelar
            </button>
          </div>
        </form>
      )}

      <div className="flex gap-2 pt-1">
        <button onClick={() => setOpen((o) => !o)} className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-800 transition-colors">
          {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          {existing ? "Editar" : "Configurar"}
        </button>
        {existing && (
          <>
            <button onClick={handleTest} disabled={testing}
              className="flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-gray-900 transition-colors disabled:opacity-50">
              {testing ? <Loader2 size={12} className="animate-spin" /> : null}
              Testar
            </button>
            {(isSuperAdmin || existing.scope === "tenant") && (
              <button
                onClick={() => { if (confirm("Remover integração?")) deleteMut.mutate(); }}
                className="ml-auto text-gray-300 hover:text-red-500 transition-colors"
              >
                <Trash2 size={13} />
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function IntegracoesTab() {
  const { user, tenant } = useAuth();
  const isSuperAdmin = user?.is_super_admin ?? false;

  const { data: integrations = [], isLoading } = useQuery({
    queryKey: ["integrations"],
    queryFn: integrationsApi.list,
  });

  const types: IntegrationType[] = ["shodan", "wazuh", "zabbix", "openvas", "nmap", "bookstack"];

  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">
        {isSuperAdmin
          ? "Configurações globais ficam disponíveis para todos os tenants como fallback."
          : "Configurações deste tenant sobrepõem as globais."}
      </p>
      {isLoading ? (
        <p className="text-sm text-gray-400">Carregando...</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {types.map((t) => {
            const tenantSpecific = integrations.find((i: Integration) => i.type === t && i.scope === "tenant");
            const global = integrations.find((i: Integration) => i.type === t && i.scope === "global");
            return (
              <IntegrationCard
                key={t} type={t}
                existing={tenantSpecific ?? global}
                tenantId={tenant?.id ?? null}
                isSuperAdmin={isSuperAdmin}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

type Tab = "tenants" | "equipe" | "politica" | "integracoes";

export function Organisation() {
  const { user, tenantRole } = useAuth();
  const isSuperAdmin = user?.is_super_admin ?? false;
  const isAdmin = isSuperAdmin || tenantRole === "admin";

  const [tab, setTab] = useState<Tab>(isSuperAdmin ? "tenants" : "equipe");

  if (!isAdmin) {
    return (
      <PageWrapper title="Organização">
        <div className="flex items-center justify-center h-64">
          <p className="text-sm text-gray-400">Acesso restrito a administradores.</p>
        </div>
      </PageWrapper>
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    ...(isSuperAdmin ? [{ id: "tenants" as Tab, label: "Tenants" }] : []),
    { id: "equipe",       label: "Equipe" },
    { id: "politica",     label: "Política" },
    { id: "integracoes",  label: "Integrações" },
  ];

  return (
    <PageWrapper title="Organização">
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex border-b border-gray-200 px-2 pt-2">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px mr-1 ${
                tab === t.id
                  ? "border-brand-600 text-brand-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="p-6">
          {tab === "tenants"      && isSuperAdmin && <TenantsTab />}
          {tab === "equipe"       && <EquipeTab />}
          {tab === "politica"     && <PoliticaTab />}
          {tab === "integracoes"  && <IntegracoesTab />}
        </div>
      </div>
    </PageWrapper>
  );
}
