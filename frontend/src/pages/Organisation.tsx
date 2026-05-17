import { Fragment, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Building2, Plus, UserPlus, Trash2, Edit2, Check, X,
  KeyRound, ToggleLeft, ToggleRight, Users, ShieldCheck,
  Globe, ChevronDown, ChevronUp, Loader2, CheckCircle2, XCircle,
  ShieldAlert, AlertTriangle, Lock, HardDrive, Cloud, Server, Play, RefreshCw, Clock,
} from "lucide-react";
import toast from "react-hot-toast";
import { useForm } from "react-hook-form";
import { PageWrapper } from "../components/layout/PageWrapper";
import { useAuth } from "../hooks/useAuth";
import { tenantsApi } from "../api/tenants";
import { inviteApi } from "../api/invite";
import { dlpApi, type DLPRule, type DLPIncident } from "../api/dlp";
import { tenantBackupApi, type BackupConfig, type BackupConfigCreate } from "../api/backup";
import { adminLlmConfigsApi, tenantLlmConfigsApi, llmProvidersApi, type LLMConfig, type LLMConfigCreate, type LLMProviderMeta } from "../api/llm_configs";
import { permissionsApi, type DeviceCategory, type FunctionalModule } from "../api/permissions";
import { integrationsApi } from "../api/integrations";
import { glpiApi } from "../api/glpi";
import { rmmApi, type RmmIntegration, type RmmType } from "../api/rmm";
import { identityApi } from "../api/identity";
import type { IdentityProvider, ProviderType } from "../types/identity";
import { auditApi } from "../api/audit";
import { AUDIT_INTENTS, type AuditPolicy, type UserForPolicy } from "../types/audit";
import type { Integration, IntegrationType } from "../types/integration";
import type { TenantMember, TenantRead, TenantRole } from "../types/tenant";

// ── Role constants ────────────────────────────────────────────────────────────

const ROLES: TenantRole[] = ["admin", "analyst_sec", "analyst_n2", "analyst_n1", "readonly"];
const ROLE_LABELS: Record<TenantRole, string> = {
  admin:       "Admin",
  analyst_sec: "Analista de SI",
  analyst_n2:  "Analista N2",
  analyst_n1:  "Analista N1",
  readonly:    "Leitor",
  analyst:     "Analista (legado)",
};
const ROLE_COLORS: Record<TenantRole, string> = {
  admin:       "bg-brand-100 text-brand-700",
  analyst_sec: "bg-rose-100 text-rose-700",
  analyst_n2:  "bg-blue-100 text-blue-700",
  analyst_n1:  "bg-cyan-100 text-cyan-700",
  readonly:    "bg-gray-100 text-gray-600",
  analyst:     "bg-blue-100 text-blue-600",
};
const ROLE_DESCRIPTIONS: Partial<Record<TenantRole, string>> = {
  analyst_sec: "Leitura total + escrita em Alertas, Playbooks, Compliance e Remediações. Sem operações diretas em dispositivos.",
  analyst_n2:  "Executa operações de baixo risco diretamente. Operações críticas vão para fila.",
  analyst_n1:  "Todas as operações passam por fila de revisão N2.",
  readonly:    "Apenas visualização. Sem execução, remediação ou planos.",
};

function RoleBadge({ role }: { role: TenantRole }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${ROLE_COLORS[role]}`}>
      {ROLE_LABELS[role]}
    </span>
  );
}

const AUTH_SOURCE_LABELS: Record<string, string> = {
  local: "Local",
  ldap: "AD/LDAP",
  oidc: "SSO",
  break_glass: "Break-glass",
};
const AUTH_SOURCE_COLORS: Record<string, string> = {
  local: "bg-gray-100 text-gray-500",
  ldap: "bg-blue-100 text-blue-700",
  oidc: "bg-purple-100 text-purple-700",
  break_glass: "bg-red-100 text-red-700",
};

function AuthSourceBadge({ source }: { source?: string }) {
  const s = source ?? "local";
  if (s === "local") return null;
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${AUTH_SOURCE_COLORS[s] ?? AUTH_SOURCE_COLORS.local}`}>
      {AUTH_SOURCE_LABELS[s] ?? s}
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
const FUNC_MODULES: { key: FunctionalModule; label: string; group: string }[] = [
  { key: "compliance",         label: "Compliance",              group: "Conformidade"       },
  { key: "remediation",        label: "Remediação",              group: "Conformidade"       },
  { key: "server_analysis",    label: "Análise de Servidores",   group: "Infraestrutura"     },
  { key: "bulk_jobs",          label: "Jobs em Lote",            group: "Infraestrutura"     },
  { key: "alerts",             label: "Alertas & SIEM",          group: "Segurança"          },
  { key: "playbooks",          label: "SOAR Playbooks",          group: "Segurança"          },
  { key: "ai_assistant",       label: "Assistente IA",           group: "Inteligência IA"    },
  { key: "knowledge_base",     label: "Base de Conhecimento",    group: "Inteligência IA"    },
  { key: "cross_investigation", label: "Investigação Cruzada",   group: "Inteligência IA"    },
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

            {/* ── Presets rápidos ── */}
            <div>
              <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">Presets Rápidos</p>
              <div className="grid grid-cols-2 gap-2">
                {/* DBA */}
                <button
                  className="flex flex-col items-start p-3 border border-gray-200 rounded-xl hover:border-brand-400 hover:bg-brand-50 transition-colors text-left"
                  onClick={() => {
                    const cats: [DeviceCategory, TenantRole][] = [
                      ["server",     "analyst_n2"],
                      ["hypervisor", "analyst_n2"],
                      ["firewall",   "readonly"],
                      ["switch",     "readonly"],
                    ];
                    const mods: [FunctionalModule, TenantRole][] = [
                      ["server_analysis", "analyst_n2"],
                    ];
                    cats.forEach(([cat, role]) => upsertCat.mutate({ cat, role }));
                    mods.forEach(([mod, role]) => upsertMod.mutate({ mod, role }));
                  }}
                >
                  <span className="text-xs font-semibold text-gray-800">DBA</span>
                  <span className="text-[10px] text-gray-400 mt-0.5">Servidor N2, resto Leitor</span>
                </button>
                {/* Analista de SI */}
                <button
                  className="flex flex-col items-start p-3 border border-gray-200 rounded-xl hover:border-rose-400 hover:bg-rose-50 transition-colors text-left"
                  onClick={() => {
                    const cats: DeviceCategory[] = ["firewall", "switch", "server", "hypervisor"];
                    cats.forEach((cat) => upsertCat.mutate({ cat, role: "readonly" }));
                    const mods: [FunctionalModule, TenantRole][] = [
                      ["alerts",             "analyst_n2"],
                      ["playbooks",          "analyst_n2"],
                      ["compliance",         "analyst_n2"],
                      ["remediation",        "analyst_n2"],
                      ["cross_investigation","analyst_n2"],
                    ];
                    mods.forEach(([mod, role]) => upsertMod.mutate({ mod, role }));
                  }}
                >
                  <span className="text-xs font-semibold text-gray-800">Analista de SI</span>
                  <span className="text-[10px] text-gray-400 mt-0.5">Alertas/Playbooks N2, Infra Leitor</span>
                </button>
              </div>
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
                Investigação Cruzada também exige CategoryRole nos domínios consultados.
              </p>
              {(() => {
                const groups = Array.from(new Set(FUNC_MODULES.map((m) => m.group)));
                return groups.map((grp) => (
                  <div key={grp} className="mb-4">
                    <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1 px-0.5">{grp}</p>
                    <table className="w-full text-sm">
                      <tbody className="divide-y divide-gray-100">
                        {FUNC_MODULES.filter((m) => m.group === grp).map(({ key, label }) => {
                          const override = getModOverride(key);
                          return (
                            <tr key={key} className="hover:bg-gray-50">
                              <td className="py-2 pr-4 text-gray-700">{label}</td>
                              <td className="py-2">
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
                ));
              })()}
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

// ── Permission Matrix Table (todos usuários × todos domínios) ─────────────────

const CAT_COLORS: Record<TenantRole, string> = {
  admin:        "bg-brand-100 text-brand-700 border-brand-200",
  analyst_n2:   "bg-blue-100 text-blue-700 border-blue-200",
  analyst_sec:  "bg-purple-100 text-purple-700 border-purple-200",
  analyst_n1:   "bg-cyan-100 text-cyan-700 border-cyan-200",
  readonly:     "bg-gray-100 text-gray-600 border-gray-200",
  analyst:      "bg-blue-50 text-blue-500 border-blue-100",
};
const CAT_SHORT: Record<TenantRole, string> = {
  admin:        "Admin",
  analyst_n2:   "N2",
  analyst_sec:  "Sec",
  analyst_n1:   "N1",
  readonly:     "Leitor",
  analyst:      "N2",
};

function PermissionMatrixTable({ tenantId }: { tenantId: string }) {
  const qc = useQueryClient();
  const { data: profiles = [], isLoading } = useQuery({
    queryKey: ["perm-all-profiles", tenantId],
    queryFn: permissionsApi.listCategoryProfiles,
  });

  const upsertCat = useMutation({
    mutationFn: ({ userId, cat, role }: { userId: string; cat: DeviceCategory; role: TenantRole }) =>
      permissionsApi.upsertCategoryRole(userId, cat, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["perm-all-profiles", tenantId] }),
  });
  const deleteCat = useMutation({
    mutationFn: ({ userId, cat }: { userId: string; cat: DeviceCategory }) =>
      permissionsApi.deleteCategoryRole(userId, cat),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["perm-all-profiles", tenantId] }),
  });

  const handleChange = (userId: string, cat: DeviceCategory, val: TenantRole | "") => {
    if (val === "") deleteCat.mutate({ userId, cat });
    else upsertCat.mutate({ userId, cat, role: val });
  };

  if (isLoading) return <p className="text-sm text-gray-400 text-center py-8">Carregando matriz...</p>;
  if (profiles.length === 0) return <p className="text-sm text-gray-400 text-center py-8">Nenhum usuário com permissões configuradas.</p>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
        <thead className="bg-gray-50">
          <tr>
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase w-48">Usuário</th>
            <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase text-center">Base</th>
            {DEVICE_CATS.map(({ key, label }) => (
              <th key={key} className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase text-center">{label}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {profiles.map((p) => (
            <tr key={p.user_id} className="hover:bg-gray-50">
              <td className="px-4 py-2.5">
                <p className="text-sm font-medium text-gray-900 truncate max-w-[160px]">{p.user_name}</p>
                <p className="text-[11px] text-gray-400 truncate max-w-[160px]">{p.user_email}</p>
              </td>
              <td className="px-3 py-2.5 text-center">
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${CAT_COLORS[p.tenant_role] ?? CAT_COLORS.readonly}`}>
                  {CAT_SHORT[p.tenant_role] ?? p.tenant_role}
                </span>
              </td>
              {DEVICE_CATS.map(({ key }) => {
                const override = p.category_roles.find((cr) => cr.category === key)?.role;
                return (
                  <td key={key} className="px-3 py-2.5 text-center">
                    <select
                      value={override ?? ""}
                      onChange={(e) => handleChange(p.user_id, key, e.target.value as TenantRole | "")}
                      className={`border rounded px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500 ${
                        override ? `${CAT_COLORS[override]} font-semibold` : "border-gray-200 text-gray-400"
                      }`}
                    >
                      {PERM_ROLES.map((r) => (
                        <option key={r.value} value={r.value}>{r.value === "" ? "— herdar" : CAT_SHORT[r.value as TenantRole] ?? r.label}</option>
                      ))}
                    </select>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[11px] text-gray-400 mt-2 px-1">
        "— herdar" usa o perfil base do tenant. Alterações são salvas imediatamente.
      </p>
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
  const [inviteAuthSource, setInviteAuthSource] = useState("local");
  const [inviteCatOverrides, setInviteCatOverrides] = useState<Partial<Record<DeviceCategory, TenantRole | "">>>({});
  const [showDomainStep, setShowDomainStep] = useState(false);
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
        const res = await tenantsApi.inviteByEmail(tenantId, { email: inviteEmail, name: inviteName || undefined, role: inviteRole });
        const userId = res.member?.user_id ?? (res as unknown as TenantMember)?.user_id;
        if (userId) {
          await Promise.all(
            (Object.entries(inviteCatOverrides) as [DeviceCategory, TenantRole | ""][])
              .filter(([, role]) => role !== "")
              .map(([cat, role]) => permissionsApi.upsertCategoryRole(userId, cat, role as TenantRole))
          );
        }
        return res;
      }
      await inviteApi.create({ email: inviteEmail, tenant_id: tenantId, role: inviteRole, auth_source: inviteAuthSource, frontend_url: window.location.origin });
      setEmailSent(true);
      return { member: null as unknown as TenantMember, temp_password: null as string | null };
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["members", tenantId] });
      if (res?.temp_password) setTempPassword(res.temp_password);
      if (inviteMode === "direct") {
        setShowInvite(false);
        setInviteEmail(""); setInviteName(""); setInviteRole("analyst_n2");
        setInviteAuthSource("local"); setInviteCatOverrides({}); setShowDomainStep(false);
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

          {inviteMode === "direct" && (
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              <button
                type="button"
                onClick={() => setShowDomainStep((v) => !v)}
                className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-gray-600 hover:bg-gray-100 transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <ShieldCheck size={12} className="text-brand-500" />
                  Permissões por domínio <span className="text-gray-400 font-normal">(opcional)</span>
                </span>
                {showDomainStep ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              </button>
              {showDomainStep && (
                <div className="px-3 pb-3 pt-1 space-y-1 border-t border-gray-100 bg-gray-50">
                  <p className="text-[11px] text-gray-400 mb-2">
                    Deixe em "— herdar" para usar o perfil base acima. Overrides definem acesso granular por tipo de equipamento.
                  </p>
                  {DEVICE_CATS.map(({ key, label }) => (
                    <div key={key} className="flex items-center justify-between py-1">
                      <span className="text-xs text-gray-700">{label}</span>
                      <select
                        value={inviteCatOverrides[key] ?? ""}
                        onChange={(e) => setInviteCatOverrides((prev) => ({ ...prev, [key]: e.target.value as TenantRole | "" }))}
                        className={`border rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500 ${
                          inviteCatOverrides[key] ? "border-brand-300 bg-brand-50 text-brand-700" : "border-gray-200 text-gray-500"
                        }`}
                      >
                        {PERM_ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                      </select>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {inviteMode === "email" && (
            <select
              value={inviteAuthSource} onChange={(e) => setInviteAuthSource(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="local">Conta local (senha na plataforma)</option>
              <option value="ldap">Active Directory / LDAP</option>
              <option value="oidc">SSO — OIDC (Azure AD / Okta)</option>
              <option value="break_glass">Break-glass (emergência)</option>
            </select>
          )}
          {inviteMut.isError && (
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
                    <AuthSourceBadge source={m.auth_source} />
                    <button
                      onClick={() => { setPermUserId(m.user_id); setPermUserName(m.name); }}
                      className="flex items-center gap-1 text-xs text-gray-500 hover:text-brand-600 border border-gray-200 hover:border-brand-300 bg-white px-2 py-0.5 rounded transition-colors"
                      title="Editar permissões por domínio"
                    >
                      <ShieldCheck size={11} />
                      Permissões
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
          {createMut.isError && (
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
  const [view, setView] = useState<"lista" | "matriz">("lista");

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
        <div className="flex items-center gap-3 mb-4">
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
        <>
          <div className="flex gap-1 mb-5 bg-gray-100 rounded-lg p-1 w-fit">
            {(["lista", "matriz"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  view === v ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {v === "lista" ? "Lista de Membros" : "Matriz de Permissões"}
              </button>
            ))}
          </div>
          {view === "lista" ? (
            <MembersPanel
              tenantId={activeTenantId}
              tenantName={activeTenantName}
              currentUserId={user?.id ?? ""}
            />
          ) : (
            <PermissionMatrixTable tenantId={activeTenantId} />
          )}
        </>
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

const POLICY_ROLES = ["analyst_n2", "analyst_n1", "readonly"] as const;
const POLICY_ROLE_LABELS: Record<string, string> = {
  analyst_n2: "Analista N2",
  analyst_n1: "Analista N1",
  readonly:   "Leitor",
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
      { key: "snapshot_enabled",   label: "Snapshot automático",       type: "checkbox" },
      { key: "snapshot_frequency", label: "Frequência do snapshot",    type: "select", defaultValue: "daily",
        options: [{ value: "daily", label: "Diário" }, { value: "weekly", label: "Semanal" }] },
      { key: "snapshot_weekday",   label: "Dia da semana (se semanal)", type: "select", defaultValue: "1",
        options: [
          { value: "0", label: "Segunda-feira" },
          { value: "1", label: "Terça-feira" },
          { value: "2", label: "Quarta-feira" },
          { value: "3", label: "Quinta-feira" },
          { value: "4", label: "Sexta-feira" },
          { value: "5", label: "Sábado" },
          { value: "6", label: "Domingo" },
        ] },
      { key: "snapshot_hour",      label: "Horário do snapshot (UTC)",  type: "select", defaultValue: "2",
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
        else if (f.key === "snapshot_hour")    config[f.key] = parseInt(formData[f.key]) || 2;
        else if (f.key === "snapshot_weekday") config[f.key] = parseInt(formData[f.key]) ?? 1;
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
          {saveMut.isError && (
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

// ── GLPI Integration Card ─────────────────────────────────────────────────────

const PRIORITY_LABELS: Record<number, string> = {
  1: "Muito Baixa", 2: "Baixa", 3: "Média", 4: "Alta", 5: "Muito Alta", 6: "Crítica",
};

const TICKET_TYPE_LABELS: Record<number, string> = {
  1: "Incidente", 2: "Requisição", 3: "Problema", 4: "Mudança",
};

type GlpiFormData = {
  glpi_url: string;
  app_token: string;
  username: string;
  password: string;
  verify_ssl: boolean;
  min_priority: string;
  poll_interval_minutes: string;
  lookback_hours: string;
  type_1: boolean;
  type_2: boolean;
  type_3: boolean;
  type_4: boolean;
  // Analysis mode & enrichment sources
  auto_analysis_enabled: boolean;
  enrich_zabbix: boolean;
  enrich_wazuh: boolean;
  enrich_device_logs: boolean;
  device_logs_timeout_seconds: string;
  auto_correlate_devices: boolean;
  unmatched_to_manual_queue: boolean;
  force_analysis_on_security: boolean;
  force_analysis_on_recurrent: boolean;
};

function GlpiIntegrationCard() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; latency_ms?: number | null } | null>(null);
  const [testing, setTesting] = useState(false);

  const { data: existing } = useQuery({
    queryKey: ["glpi-integration"],
    queryFn: glpiApi.getIntegration,
  });

  const { register, handleSubmit, reset, watch, formState: { isSubmitting } } = useForm<GlpiFormData>({
    defaultValues: {
      glpi_url: "", app_token: "", username: "", password: "",
      verify_ssl: true, min_priority: "3", poll_interval_minutes: "5", lookback_hours: "24",
      type_1: true, type_2: true, type_3: false, type_4: false,
      auto_analysis_enabled: true,
      enrich_zabbix: false, enrich_wazuh: false, enrich_device_logs: false,
      device_logs_timeout_seconds: "30",
      auto_correlate_devices: true, unmatched_to_manual_queue: true,
      force_analysis_on_security: true, force_analysis_on_recurrent: false,
    },
  });

  const autoAnalysis = watch("auto_analysis_enabled");
  const enrichDeviceLogs = watch("enrich_device_logs");

  useEffect(() => {
    if (!open || !existing) return;
    reset({
      glpi_url: existing.glpi_url,
      app_token: existing.app_token,
      username: existing.username,
      password: "",
      verify_ssl: existing.verify_ssl,
      min_priority: String(existing.min_priority),
      poll_interval_minutes: String(existing.poll_interval_minutes),
      lookback_hours: String(existing.lookback_hours),
      type_1: existing.trigger_types.includes(1),
      type_2: existing.trigger_types.includes(2),
      type_3: existing.trigger_types.includes(3),
      type_4: existing.trigger_types.includes(4),
      auto_analysis_enabled: existing.auto_analysis_enabled ?? true,
      enrich_zabbix: existing.enrich_zabbix ?? false,
      enrich_wazuh: existing.enrich_wazuh ?? false,
      enrich_device_logs: existing.enrich_device_logs ?? false,
      device_logs_timeout_seconds: String(existing.device_logs_timeout_seconds ?? 30),
      auto_correlate_devices: existing.auto_correlate_devices ?? true,
      unmatched_to_manual_queue: existing.unmatched_to_manual_queue ?? true,
      force_analysis_on_security: existing.force_analysis_on_security ?? true,
      force_analysis_on_recurrent: existing.force_analysis_on_recurrent ?? false,
    });
  }, [open, existing]);

  const saveMut = useMutation({
    mutationFn: async (fd: GlpiFormData) => {
      const types = ([1, 2, 3, 4] as const).filter((n) => fd[`type_${n}`]);
      const payload = {
        glpi_url:              fd.glpi_url,
        app_token:             fd.app_token,
        username:              fd.username,
        verify_ssl:            fd.verify_ssl,
        min_priority:          parseInt(fd.min_priority) || 3,
        trigger_types:         types,
        poll_interval_minutes: parseInt(fd.poll_interval_minutes) || 5,
        lookback_hours:        parseInt(fd.lookback_hours) || 24,
        auto_analysis_enabled:        fd.auto_analysis_enabled,
        enrich_zabbix:                fd.enrich_zabbix,
        enrich_wazuh:                 fd.enrich_wazuh,
        enrich_device_logs:           fd.enrich_device_logs,
        device_logs_timeout_seconds:  parseInt(fd.device_logs_timeout_seconds) || 30,
        auto_correlate_devices:       fd.auto_correlate_devices,
        unmatched_to_manual_queue:    fd.unmatched_to_manual_queue,
        force_analysis_on_security:   fd.force_analysis_on_security,
        force_analysis_on_recurrent:  fd.force_analysis_on_recurrent,
        ...(fd.password ? { password: fd.password } : {}),
      };
      if (existing) return glpiApi.updateIntegration(existing.id, payload);
      return glpiApi.createIntegration({ ...payload, password: fd.password });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["glpi-integration"] }); setOpen(false); setTestResult(null); },
  });

  const deleteMut = useMutation({
    mutationFn: () => glpiApi.deleteIntegration(existing!.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["glpi-integration"] }); setTestResult(null); },
  });

  const handleTest = async () => {
    if (!existing) return;
    setTesting(true); setTestResult(null);
    try {
      setTestResult(await glpiApi.testIntegration(existing.id));
    } catch {
      setTestResult({ success: false, message: "Erro ao testar conexão" });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className={`bg-white rounded-xl border ${existing?.is_active ? "border-gray-200" : "border-gray-100 opacity-60"} p-5 flex flex-col gap-3`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-violet-100 text-violet-700">GLPI</span>
            <span className="flex items-center gap-1 text-xs bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full">
              <Building2 size={10} />Tenant
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">Help desk — análise automática de tickets com IA.</p>
        </div>
        {existing
          ? <CheckCircle2 size={18} className="text-green-500 shrink-0" />
          : <XCircle    size={18} className="text-gray-300 shrink-0" />}
      </div>

      {testResult && (
        <div className={`text-xs rounded-lg px-3 py-2 ${testResult.success ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>
          {testResult.success ? "✓" : "✗"} {testResult.message}
          {testResult.latency_ms != null && <span className="ml-2 text-gray-400">{testResult.latency_ms.toFixed(0)}ms</span>}
        </div>
      )}

      {open && (
        <form
          onSubmit={handleSubmit((d) => saveMut.mutate(d))}
          className="space-y-3 pt-2 border-t border-gray-100"
        >
          {/* ── Conexão ──────────────────────────────────────────────────── */}
          {[
            { key: "glpi_url",   label: "URL do GLPI",   placeholder: "https://glpi.empresa.com" },
            { key: "app_token",  label: "App-Token",      placeholder: "Token da aplicação API" },
            { key: "username",   label: "Usuário",        placeholder: "glpi_api" },
          ].map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
              <input
                {...register(key as "glpi_url" | "app_token" | "username")}
                placeholder={placeholder}
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          ))}

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Senha {existing && <span className="text-gray-400 font-normal">(deixe vazio para manter a atual)</span>}
            </label>
            <input
              type="password" {...register("password")}
              placeholder={existing ? "••••••••" : "Senha do usuário GLPI"}
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          {/* ── Filtros ───────────────────────────────────────────────────── */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Prioridade mínima</label>
            <select {...register("min_priority")} className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
              {Object.entries(PRIORITY_LABELS).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Tipos de ticket</label>
            <div className="flex flex-wrap gap-3">
              {([1, 2, 3, 4] as const).map((n) => (
                <label key={n} className="flex items-center gap-1.5 text-xs cursor-pointer">
                  <input type="checkbox" {...register(`type_${n}` as "type_1" | "type_2" | "type_3" | "type_4")} className="rounded" />
                  {TICKET_TYPE_LABELS[n]}
                </label>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Poll (minutos)</label>
              <input type="number" min="1" max="60" {...register("poll_interval_minutes")} className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Lookback (horas)</label>
              <input type="number" min="1" max="168" {...register("lookback_hours")} className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
          </div>

          <label className="flex items-center gap-2 text-xs cursor-pointer">
            <input type="checkbox" {...register("verify_ssl")} className="rounded" />
            Verificar certificado SSL
          </label>

          {/* ── Análise automática ────────────────────────────────────────── */}
          <div className="pt-2 border-t border-gray-100">
            <p className="text-xs font-semibold text-gray-700 mb-2">Análise automática</p>

            <label className="flex items-center gap-2 text-xs cursor-pointer mb-3">
              <input type="checkbox" {...register("auto_analysis_enabled")} className="rounded" />
              <span className="font-medium">Análise automática ativada</span>
              <span className="text-gray-400">(Claude analisa cada ticket novo)</span>
            </label>

            {autoAnalysis && (
              <div className="space-y-2 pl-4 border-l-2 border-brand-100">
                {/* Fontes de enriquecimento */}
                <p className="text-xs font-medium text-gray-600 mb-1">Fontes de contexto</p>
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <input type="checkbox" {...register("enrich_zabbix")} className="rounded" />
                  Zabbix — métricas e triggers das últimas 24h
                </label>
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <input type="checkbox" {...register("enrich_wazuh")} className="rounded" />
                  Wazuh — alertas de segurança das últimas 24h
                </label>
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <input type="checkbox" {...register("enrich_device_logs")} className="rounded" />
                  Logs do dispositivo via SSH
                </label>

                {enrichDeviceLogs && (
                  <div className="flex items-center gap-2 pl-5">
                    <label className="text-xs text-gray-600 whitespace-nowrap">Timeout SSH (seg):</label>
                    <input
                      type="number" min="5" max="300"
                      {...register("device_logs_timeout_seconds")}
                      className="w-20 border border-gray-300 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>
                )}

                {/* Correlação de dispositivos */}
                <p className="text-xs font-medium text-gray-600 mt-3 mb-1">Correlação de dispositivos</p>
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <input type="checkbox" {...register("auto_correlate_devices")} className="rounded" />
                  Correlacionar automaticamente (IP/hostname no texto)
                </label>
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <input type="checkbox" {...register("unmatched_to_manual_queue")} className="rounded" />
                  Sem correlação → fila manual (não consome tokens)
                </label>

                {/* Overrides de filtro */}
                <p className="text-xs font-medium text-gray-600 mt-3 mb-1">Ignorar filtro de prioridade para</p>
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <input type="checkbox" {...register("force_analysis_on_security")} className="rounded" />
                  Incidentes de segurança (sempre analisar)
                </label>
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <input type="checkbox" {...register("force_analysis_on_recurrent")} className="rounded" />
                  Tickets recorrentes (sempre analisar)
                </label>
              </div>
            )}

            {!autoAnalysis && (
              <p className="text-xs text-gray-400 pl-4 border-l-2 border-gray-100">
                Tickets serão capturados e exibidos no FireManager, mas a análise precisará ser acionada manualmente.
              </p>
            )}
          </div>

          {saveMut.isError && (
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

      <div className="flex gap-2 pt-1 flex-wrap">
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
            <button onClick={() => navigate("/glpi")}
              className="flex items-center gap-1 text-xs font-medium text-violet-600 hover:text-violet-800 transition-colors">
              Ver análises →
            </button>
            <button
              onClick={() => { if (confirm("Remover integração GLPI?")) deleteMut.mutate(); }}
              className="ml-auto text-gray-300 hover:text-red-500 transition-colors"
            >
              <Trash2 size={13} />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ── LLM Providers Section ─────────────────────────────────────────────────────

const PROVIDER_COLORS: Record<string, string> = {
  anthropic:  "bg-[#cc785c] text-white",
  openai:     "bg-[#10a37f] text-white",
  google:     "bg-[#4285f4] text-white",
  deepseek:   "bg-[#1a6efd] text-white",
  moonshot:   "bg-[#7c3aed] text-white",
  xai:        "bg-gray-900 text-white",
  perplexity: "bg-[#20b2aa] text-white",
  nvidia:     "bg-[#76b900] text-white",
  zhipu:      "bg-[#2563eb] text-white",
  minimax:    "bg-[#e11d48] text-white",
  ollama:     "bg-[#374151] text-white",
};

const PROVIDER_INITIALS: Record<string, string> = {
  anthropic: "Cl", openai: "GP", google: "Gm", deepseek: "DS",
  moonshot: "Ki", xai: "Gr", perplexity: "Px", nvidia: "Nv",
  zhipu: "GL", minimax: "Mx", ollama: "Ol",
};

function LLMProvidersSection({ isSuperAdmin }: { isSuperAdmin: boolean }) {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; message: string; latency_ms: number }>>({});
  const [testing, setTesting] = useState<string | null>(null);

  // Super admin sem tenant_id no JWT deve usar adminLlmConfigsApi (rota /admin/llm-configs)
  const configsApi = isSuperAdmin ? adminLlmConfigsApi : tenantLlmConfigsApi;
  const queryKey = isSuperAdmin ? "llm-configs-global" : "llm-configs-tenant";

  const { data: configs = [], isLoading } = useQuery({
    queryKey: [queryKey],
    queryFn: configsApi.list,
  });

  const { data: providersMeta = [] } = useQuery({
    queryKey: ["llm-providers-meta"],
    queryFn: llmProvidersApi.listMeta,
  });

  const createMut = useMutation({
    mutationFn: (data: LLMConfigCreate) => configsApi.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: [queryKey] }); setShowForm(false); toast.success("Provider configurado."); },
    onError: () => toast.error("Erro ao salvar configuração."),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => configsApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: [queryKey] }); toast.success("Provider removido."); },
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, is_enabled }: { id: string; is_enabled: boolean }) =>
      configsApi.update(id, { is_enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: [queryKey] }),
  });

  const setDefaultMut = useMutation({
    mutationFn: (id: string) => configsApi.update(id, { is_default: true }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: [queryKey] }); toast.success("Provider padrão definido."); },
  });

  const handleTest = async (id: string) => {
    setTesting(id);
    try {
      const result = await configsApi.test(id);
      setTestResults((prev) => ({ ...prev, [id]: result }));
    } catch {
      setTestResults((prev) => ({ ...prev, [id]: { ok: false, message: "Erro ao testar", latency_ms: 0 } }));
    } finally {
      setTesting(null);
    }
  };

  const tenantOwned = configs.filter((c) => c.scope === "tenant");
  const globalInherited = configs.filter((c) => c.scope === "global");

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">Provedores de LLM</h3>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 text-xs bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg transition-colors"
        >
          <Plus size={13} /> Adicionar provider
        </button>
      </div>

      {showForm && (
        <LLMProviderForm
          providersMeta={providersMeta}
          onSubmit={(data) => createMut.mutate(data)}
          onCancel={() => setShowForm(false)}
          loading={createMut.isPending}
        />
      )}

      {isLoading && <p className="text-xs text-gray-400">Carregando...</p>}

      {tenantOwned.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
          {tenantOwned.map((cfg) => (
            <LLMProviderCard
              key={cfg.id}
              cfg={cfg}
              testResult={testResults[cfg.id]}
              testing={testing === cfg.id}
              onTest={() => handleTest(cfg.id)}
              onToggle={() => toggleMut.mutate({ id: cfg.id, is_enabled: !cfg.is_enabled })}
              onSetDefault={() => setDefaultMut.mutate(cfg.id)}
              onDelete={() => { if (window.confirm("Remover este provider?")) deleteMut.mutate(cfg.id); }}
            />
          ))}
        </div>
      )}

      {globalInherited.length > 0 && (
        <div>
          <p className="text-xs text-gray-400 mb-2 flex items-center gap-1">
            <Globe size={11} /> Configurações globais herdadas (somente leitura neste tenant)
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {globalInherited.map((cfg) => (
              <LLMProviderCard
                key={cfg.id}
                cfg={cfg}
                testResult={testResults[cfg.id]}
                testing={testing === cfg.id}
                onTest={() => handleTest(cfg.id)}
                readonly
              />
            ))}
          </div>
        </div>
      )}

      {!isLoading && tenantOwned.length === 0 && globalInherited.length === 0 && (
        <p className="text-xs text-gray-400 py-4 text-center">
          Nenhum provider configurado. Adicione um ou configure globalmente no PlatformConfig.
        </p>
      )}
    </div>
  );
}

function LLMProviderCard({
  cfg, testResult, testing, onTest, onToggle, onSetDefault, onDelete, readonly = false,
}: {
  cfg: LLMConfig;
  testResult?: { ok: boolean; message: string; latency_ms: number };
  testing: boolean;
  onTest: () => void;
  onToggle?: () => void;
  onSetDefault?: () => void;
  onDelete?: () => void;
  readonly?: boolean;
}) {
  const colorClass = PROVIDER_COLORS[cfg.provider] ?? "bg-gray-500 text-white";
  const initials = PROVIDER_INITIALS[cfg.provider] ?? cfg.provider.slice(0, 2).toUpperCase();

  return (
    <div className={`border rounded-lg p-4 space-y-2 ${!cfg.is_enabled ? "opacity-60" : ""} ${cfg.is_default ? "border-brand-400" : "border-gray-200"}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 ${colorClass}`}>
            {initials}
          </span>
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-800 truncate">{cfg.display_name}</p>
            <p className="text-xs text-gray-400 font-mono truncate">{cfg.model_name}</p>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {cfg.is_default && (
            <span className="text-xs bg-brand-100 text-brand-700 px-1.5 py-0.5 rounded font-medium">padrão</span>
          )}
          {cfg.no_train_flag && (
            <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded" title="Dados não usados para treinamento">🔒</span>
          )}
          {!cfg.has_key && cfg.provider !== "ollama" && (
            <span className="text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">sem key</span>
          )}
        </div>
      </div>

      {cfg.api_base_url && (
        <p className="text-xs text-gray-400 truncate font-mono">{cfg.api_base_url}</p>
      )}

      {testResult && (
        <div className={`text-xs px-2 py-1 rounded flex items-center gap-1 ${testResult.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>
          {testResult.ok ? <Check size={11} /> : <X size={11} />}
          {testResult.message}
          {testResult.ok && <span className="ml-auto text-gray-400">{testResult.latency_ms}ms</span>}
        </div>
      )}

      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={onTest}
          disabled={testing}
          className="text-xs text-gray-500 hover:text-brand-600 flex items-center gap-1 disabled:opacity-40"
        >
          {testing ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
          Testar
        </button>
        {!readonly && (
          <>
            <button onClick={onToggle} className="text-xs text-gray-500 hover:text-gray-700">
              {cfg.is_enabled ? <ToggleRight size={14} className="text-green-500" /> : <ToggleLeft size={14} />}
            </button>
            {!cfg.is_default && (
              <button onClick={onSetDefault} className="text-xs text-gray-500 hover:text-brand-600 ml-auto">
                Definir padrão
              </button>
            )}
            <button onClick={onDelete} className="text-xs text-red-400 hover:text-red-600 ml-auto">
              <Trash2 size={12} />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function LLMProviderForm({
  providersMeta, onSubmit, onCancel, loading,
}: {
  providersMeta: LLMProviderMeta[];
  onSubmit: (data: LLMConfigCreate) => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [noTrain, setNoTrain] = useState(true);

  const meta = providersMeta.find((m) => m.provider === provider);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      provider,
      model_name: model || meta?.default_model || "gpt-4o",
      api_key: apiKey || null,
      api_base_url: baseUrl || null,
      is_default: isDefault,
      no_train_flag: noTrain,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="border border-gray-200 rounded-lg p-4 mb-4 space-y-3 bg-gray-50">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Provider</label>
          <select
            value={provider}
            onChange={(e) => { setProvider(e.target.value); setModel(""); setBaseUrl(""); }}
            className="w-full text-sm border border-gray-200 rounded px-2 py-1.5 bg-white"
          >
            {providersMeta.map((m) => (
              <option key={m.provider} value={m.provider}>{m.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Modelo</label>
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={meta?.default_model ?? "modelo"}
            className="w-full text-sm border border-gray-200 rounded px-2 py-1.5"
          />
        </div>
      </div>

      {meta?.needs_key && (
        <div>
          <label className="text-xs text-gray-500 mb-1 block">API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
            className="w-full text-sm border border-gray-200 rounded px-2 py-1.5 font-mono"
          />
        </div>
      )}

      {(provider === "ollama" || !meta?.base_url) && (
        <div>
          <label className="text-xs text-gray-500 mb-1 block">URL Base {provider === "ollama" ? "(ex: http://192.168.1.10:11434/v1)" : "(opcional)"}</label>
          <input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={meta?.base_url ?? "https://..."}
            className="w-full text-sm border border-gray-200 rounded px-2 py-1.5 font-mono"
          />
        </div>
      )}

      <div className="flex items-center gap-4 text-sm">
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
          <span className="text-xs text-gray-600">Definir como padrão</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={noTrain} onChange={(e) => setNoTrain(e.target.checked)} />
          <span className="text-xs text-gray-600">🔒 Não usar para treinamento</span>
        </label>
      </div>

      <div className="flex gap-2 justify-end">
        <button type="button" onClick={onCancel} className="text-sm text-gray-500 hover:text-gray-700 px-3 py-1.5">
          Cancelar
        </button>
        <button
          type="submit"
          disabled={loading}
          className="text-sm bg-brand-600 hover:bg-brand-700 text-white px-4 py-1.5 rounded-lg disabled:opacity-50"
        >
          {loading ? "Salvando..." : "Salvar"}
        </button>
      </div>
    </form>
  );
}

// ── RMM Integrations Section ─────────────────────────────────────────────────

const RMM_TYPE_META: { value: RmmType; label: string; color: string; authFields: { key: string; label: string; type?: string }[] }[] = [
  { value: "tactical_rmm",        label: "Tactical RMM",          color: "bg-indigo-100 text-indigo-700",  authFields: [{ key: "api_key", label: "API Key", type: "password" }] },
  { value: "ninja_rmm",           label: "NinjaRMM (NinjaOne)",   color: "bg-sky-100 text-sky-700",        authFields: [{ key: "client_id", label: "Client ID" }, { key: "client_secret", label: "Client Secret", type: "password" }] },
  { value: "atera",               label: "Atera",                  color: "bg-teal-100 text-teal-700",      authFields: [{ key: "api_key", label: "API Key", type: "password" }] },
  { value: "connectwise_automate",label: "ConnectWise Automate",   color: "bg-orange-100 text-orange-700",  authFields: [{ key: "username", label: "Usuário" }, { key: "password", label: "Senha", type: "password" }] },
];

function RmmIntegrationsSection() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<{
    name: string; rmm_type: RmmType; base_url: string; credentials: Record<string, string>; site_filter: string;
  }>({ name: "", rmm_type: "tactical_rmm", base_url: "", credentials: {}, site_filter: "" });
  const [editForm, setEditForm] = useState<{
    name: string; base_url: string; credentials: Record<string, string>; site_filter: string;
  }>({ name: "", base_url: "", credentials: {}, site_filter: "" });

  const { data: integrations = [], isLoading } = useQuery<RmmIntegration[]>({
    queryKey: ["rmm-integrations"],
    queryFn: rmmApi.list,
  });

  const createMut = useMutation({
    mutationFn: () => rmmApi.create({ name: form.name, rmm_type: form.rmm_type, base_url: form.base_url, credentials: form.credentials, site_filter: form.site_filter || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rmm-integrations"] });
      setShowForm(false);
      setForm({ name: "", rmm_type: "tactical_rmm", base_url: "", credentials: {}, site_filter: "" });
      toast.success("Integração RMM criada.");
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao criar.";
      toast.error(msg);
    },
  });

  const updateMut = useMutation({
    mutationFn: (id: string) => {
      const hasCredentials = Object.values(editForm.credentials).some((v) => v.trim() !== "");
      return rmmApi.update(id, {
        name: editForm.name,
        base_url: editForm.base_url,
        site_filter: editForm.site_filter || null,
        ...(hasCredentials ? { credentials: editForm.credentials } : {}),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rmm-integrations"] });
      setEditingId(null);
      toast.success("Integração atualizada.");
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao salvar.";
      toast.error(msg);
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => rmmApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rmm-integrations"] }); toast.success("Integração removida."); },
    onError: () => toast.error("Erro ao remover."),
  });

  const handleTest = async (id: string) => {
    try {
      const r = await rmmApi.test(id);
      r.ok ? toast.success(r.message) : toast.error(r.message);
    } catch { toast.error("Erro ao testar conexão."); }
  };

  const handleSync = async (id: string) => {
    setSyncing(id);
    try {
      const r = await rmmApi.sync(id);
      toast.success(r.message);
      qc.invalidateQueries({ queryKey: ["rmm-integrations"] });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao sincronizar.";
      toast.error(msg);
    } finally { setSyncing(null); }
  };

  const handleStartEdit = (intg: RmmIntegration) => {
    setEditingId(intg.id);
    setEditForm({ name: intg.name, base_url: intg.base_url, credentials: {}, site_filter: intg.site_filter ?? "" });
  };

  const selectedTypeMeta = RMM_TYPE_META.find((t) => t.value === form.rmm_type);

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">RMM (Remote Monitoring & Management)</h3>
          <p className="text-xs text-gray-400 mt-0.5">Tactical RMM · NinjaRMM · Atera · ConnectWise Automate</p>
        </div>
        <button
          onClick={() => { setShowForm((v) => !v); setEditingId(null); }}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 text-white rounded-lg text-xs hover:bg-brand-700"
        >
          <Plus size={13} /> Nova Integração RMM
        </button>
      </div>

      {showForm && (
        <div className="border border-gray-200 rounded-xl p-4 mb-4 bg-gray-50">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-600">Nome</label>
              <input className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Ex: RMM Produção" />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600">Tipo</label>
              <select className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" value={form.rmm_type} onChange={(e) => setForm({ ...form, rmm_type: e.target.value as RmmType, credentials: {} })}>
                {RMM_TYPE_META.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-600">URL Base da API</label>
              <input className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.seurmm.com" />
            </div>
            {selectedTypeMeta?.authFields.map((field) => (
              <div key={field.key}>
                <label className="text-xs font-medium text-gray-600">{field.label}</label>
                <input type={field.type || "text"} className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" value={form.credentials[field.key] || ""} onChange={(e) => setForm({ ...form, credentials: { ...form.credentials, [field.key]: e.target.value } })} />
              </div>
            ))}
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-600">Filtro de Site/Cliente <span className="text-gray-400 font-normal">(opcional)</span></label>
              <input className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" value={form.site_filter} onChange={(e) => setForm({ ...form, site_filter: e.target.value })} placeholder="Ex: Clínica São Lucas, Hospital ABC (separe por vírgula)" />
              <p className="text-[10px] text-gray-400 mt-1">Filtra agentes pelo site_name ou client_name no RMM. Deixe vazio para sincronizar todos.</p>
            </div>
          </div>
          <div className="flex gap-2 mt-3">
            <button onClick={() => createMut.mutate()} disabled={createMut.isPending || !form.name || !form.base_url} className="px-4 py-1.5 bg-brand-600 text-white rounded-lg text-xs hover:bg-brand-700 disabled:opacity-50">
              {createMut.isPending ? "Criando..." : "Criar"}
            </button>
            <button onClick={() => setShowForm(false)} className="px-4 py-1.5 bg-white border border-gray-200 text-gray-600 rounded-lg text-xs hover:bg-gray-50">Cancelar</button>
          </div>
        </div>
      )}

      {isLoading && <p className="text-xs text-gray-400">Carregando...</p>}
      {!isLoading && integrations.length === 0 && !showForm && (
        <p className="text-xs text-gray-400 py-3 text-center border border-dashed border-gray-200 rounded-xl">Nenhuma integração RMM configurada.</p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {integrations.map((intg) => {
          const meta = RMM_TYPE_META.find((t) => t.value === intg.rmm_type);
          const isEditing = editingId === intg.id;

          if (isEditing) {
            return (
              <div key={intg.id} className="border border-brand-300 rounded-xl p-4 bg-brand-50 col-span-1 sm:col-span-2">
                <p className="text-xs font-semibold text-brand-700 mb-3">Editar — {intg.name}</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-gray-600">Nome</label>
                    <input className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600">URL Base da API</label>
                    <input className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" value={editForm.base_url} onChange={(e) => setEditForm({ ...editForm, base_url: e.target.value })} />
                  </div>
                  {meta?.authFields.map((field) => (
                    <div key={field.key}>
                      <label className="text-xs font-medium text-gray-600">{field.label} <span className="text-gray-400 font-normal">(deixe vazio para manter)</span></label>
                      <input type={field.type || "text"} className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" placeholder="••••••••" value={editForm.credentials[field.key] || ""} onChange={(e) => setEditForm({ ...editForm, credentials: { ...editForm.credentials, [field.key]: e.target.value } })} />
                    </div>
                  ))}
                  <div className="col-span-2">
                    <label className="text-xs font-medium text-gray-600">Filtro de Site/Cliente <span className="text-gray-400 font-normal">(opcional)</span></label>
                    <input className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" value={editForm.site_filter} onChange={(e) => setEditForm({ ...editForm, site_filter: e.target.value })} placeholder="Ex: Clínica São Lucas, Hospital ABC" />
                  </div>
                </div>
                <div className="flex gap-2 mt-3">
                  <button onClick={() => updateMut.mutate(intg.id)} disabled={updateMut.isPending || !editForm.name || !editForm.base_url} className="px-4 py-1.5 bg-brand-600 text-white rounded-lg text-xs hover:bg-brand-700 disabled:opacity-50">
                    {updateMut.isPending ? "Salvando..." : "Salvar"}
                  </button>
                  <button onClick={() => setEditingId(null)} className="px-4 py-1.5 bg-white border border-gray-200 text-gray-600 rounded-lg text-xs hover:bg-gray-50">Cancelar</button>
                </div>
              </div>
            );
          }

          return (
            <div key={intg.id} className="border border-gray-200 rounded-xl p-4 bg-white">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${meta?.color ?? "bg-gray-100 text-gray-600"}`}>{meta?.label ?? intg.rmm_type}</span>
                    {intg.is_active
                      ? <span className="text-[10px] text-green-600 font-medium">● Ativa</span>
                      : <span className="text-[10px] text-gray-400">○ Inativa</span>}
                  </div>
                  <p className="font-semibold text-sm text-gray-800 mt-1.5">{intg.name}</p>
                  <p className="text-xs text-gray-400 truncate">{intg.base_url}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 mt-3 text-xs text-gray-500">
                <span><strong className="text-gray-800">{intg.agent_count}</strong> agentes</span>
                {intg.last_sync_status === "ok" && <span className="flex items-center gap-1 text-green-600"><CheckCircle2 size={11} />Sync OK</span>}
                {intg.last_sync_status === "error" && <span className="flex items-center gap-1 text-red-500"><XCircle size={11} />Erro</span>}
              </div>
              {intg.site_filter && (
                <p className="text-[10px] text-gray-400 mt-1.5 truncate">
                  <span className="font-medium">Filtro:</span> {intg.site_filter}
                </p>
              )}
              <div className="flex items-center gap-1 mt-3 pt-3 border-t border-gray-100">
                <button onClick={() => handleTest(intg.id)} title="Testar conexão" className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-brand-600 hover:bg-brand-50 rounded transition-colors">
                  <Play size={11} /> Testar
                </button>
                <button onClick={() => handleSync(intg.id)} disabled={syncing === intg.id} title="Sincronizar agentes" className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-green-600 hover:bg-green-50 rounded transition-colors disabled:opacity-50">
                  {syncing === intg.id ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />} Sincronizar
                </button>
                <button onClick={() => handleStartEdit(intg)} title="Editar integração" className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-brand-600 hover:bg-brand-50 rounded transition-colors">
                  <Edit2 size={11} /> Editar
                </button>
                <button onClick={() => { if (confirm(`Remover "${intg.name}" e todos os seus agentes?`)) deleteMut.mutate(intg.id); }} className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-red-500 hover:bg-red-50 rounded transition-colors ml-auto">
                  <Trash2 size={11} /> Remover
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Identity Providers Section ────────────────────────────────────────────────

const IDENTITY_PROVIDER_META: { value: ProviderType; label: string; color: string; fields: { key: string; label: string; type?: string; placeholder?: string }[] }[] = [
  {
    value: "local_ad",
    label: "Active Directory (LDAP)",
    color: "bg-purple-100 text-purple-700",
    fields: [
      { key: "host",     label: "Host / IP",   placeholder: "192.168.1.10" },
      { key: "port",     label: "Porta",        placeholder: "389" },
      { key: "base_dn",  label: "Base DN",      placeholder: "DC=empresa,DC=local" },
      { key: "username", label: "Bind DN",      placeholder: "CN=svc_eternity,CN=Users,DC=empresa,DC=local" },
      { key: "password", label: "Senha Bind",   type: "password" },
    ],
  },
  {
    value: "azure_ad",
    label: "Azure AD / Entra ID",
    color: "bg-blue-100 text-blue-700",
    fields: [
      { key: "tenant_id",     label: "Tenant ID (Directory ID)", placeholder: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" },
      { key: "client_id",     label: "Client ID (App ID)",       placeholder: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" },
      { key: "client_secret", label: "Client Secret",            type: "password" },
    ],
  },
  {
    value: "google_workspace",
    label: "Google Workspace",
    color: "bg-red-100 text-red-700",
    fields: [
      { key: "domain",           label: "Domínio",                  placeholder: "minhaempresa.com" },
      { key: "credentials_json", label: "JSON da Service Account",  placeholder: '{"type": "service_account", ...}' },
    ],
  },
];

function IdentityProvidersSection() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [providerType, setProviderType] = useState<ProviderType>("local_ad");
  const [providerName, setProviderName] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  const { data: providers = [], isLoading } = useQuery<IdentityProvider[]>({
    queryKey: ["identity-providers"],
    queryFn: identityApi.listProviders,
  });

  const createMut = useMutation({
    mutationFn: () => {
      const config: Record<string, unknown> = { ...fields };
      if (providerType === "local_ad") config.port = parseInt(fields.port || "389", 10);
      return identityApi.createProvider({ name: providerName, provider_type: providerType, config });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["identity-providers"] });
      setShowForm(false);
      setProviderName(""); setFields({});
      toast.success("Provedor adicionado.");
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao adicionar.";
      toast.error(msg);
    },
  });

  const syncMut = useMutation({
    mutationFn: identityApi.syncProvider,
    onSuccess: (p) => {
      toast.success(`${(p as IdentityProvider).last_sync_count ?? 0} usuários sincronizados`);
      qc.invalidateQueries({ queryKey: ["identity-providers"] });
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro na sincronização.";
      toast.error(msg);
    },
  });

  const testMut = useMutation({
    mutationFn: identityApi.testProvider,
    onSuccess: (r) => {
      const res = r as { success: boolean; message: string };
      res.success ? toast.success(res.message) : toast.error(res.message);
    },
    onError: () => toast.error("Erro ao testar conexão."),
  });

  const deleteMut = useMutation({
    mutationFn: identityApi.deleteProvider,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["identity-providers"] });
      toast.success("Provedor removido.");
    },
    onError: () => toast.error("Erro ao remover."),
  });

  const selectedMeta = IDENTITY_PROVIDER_META.find((m) => m.value === providerType);

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Gestão de Identidade / Diretórios</h3>
          <p className="text-xs text-gray-400 mt-0.5">Active Directory (LDAP) · Azure AD / Entra ID · Google Workspace</p>
        </div>
        <button
          onClick={() => { setShowForm((v) => !v); setFields({}); }}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 text-white rounded-lg text-xs hover:bg-brand-700"
        >
          <Plus size={13} /> Adicionar Provedor
        </button>
      </div>

      {showForm && (
        <div className="border border-gray-200 rounded-xl p-4 mb-4 bg-gray-50">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-600">Nome</label>
              <input className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" value={providerName} onChange={(e) => setProviderName(e.target.value)} placeholder="Ex: AD Corporativo" />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600">Tipo</label>
              <select className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" value={providerType} onChange={(e) => { setProviderType(e.target.value as ProviderType); setFields({}); }}>
                {IDENTITY_PROVIDER_META.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>
            {selectedMeta?.fields.map((field) => (
              <div key={field.key} className={field.key === "credentials_json" ? "col-span-2" : ""}>
                <label className="text-xs font-medium text-gray-600">{field.label}</label>
                {field.key === "credentials_json" ? (
                  <textarea rows={3} className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white font-mono" value={fields[field.key] || ""} onChange={(e) => setFields({ ...fields, [field.key]: e.target.value })} placeholder={field.placeholder} />
                ) : (
                  <input type={field.type || "text"} className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" value={fields[field.key] || ""} onChange={(e) => setFields({ ...fields, [field.key]: e.target.value })} placeholder={field.placeholder} />
                )}
              </div>
            ))}
          </div>
          <div className="flex gap-2 mt-3">
            <button onClick={() => createMut.mutate()} disabled={createMut.isPending || !providerName} className="px-4 py-1.5 bg-brand-600 text-white rounded-lg text-xs hover:bg-brand-700 disabled:opacity-50">
              {createMut.isPending ? "Adicionando..." : "Adicionar"}
            </button>
            <button onClick={() => setShowForm(false)} className="px-4 py-1.5 bg-white border border-gray-200 text-gray-600 rounded-lg text-xs hover:bg-gray-50">Cancelar</button>
          </div>
        </div>
      )}

      {isLoading && <p className="text-xs text-gray-400">Carregando...</p>}
      {!isLoading && providers.length === 0 && !showForm && (
        <p className="text-xs text-gray-400 py-3 text-center border border-dashed border-gray-200 rounded-xl">Nenhum provedor de identidade configurado.</p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {providers.map((p) => {
          const meta = IDENTITY_PROVIDER_META.find((m) => m.value === p.provider_type);
          return (
            <div key={p.id} className="border border-gray-200 rounded-xl p-4 bg-white">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${meta?.color ?? "bg-gray-100 text-gray-600"}`}>{meta?.label ?? p.provider_type}</span>
                    {p.is_active
                      ? <span className="text-[10px] text-green-600 font-medium">● Ativo</span>
                      : <span className="text-[10px] text-gray-400">○ Inativo</span>}
                  </div>
                  <p className="font-semibold text-sm text-gray-800 mt-1.5">{p.name}</p>
                  <p className="text-xs text-gray-400">
                    {p.last_sync_at
                      ? `Última sync: ${new Date(p.last_sync_at).toLocaleDateString("pt-BR")} · ${p.last_sync_count ?? 0} usuários`
                      : "Nunca sincronizado"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1 mt-3 pt-3 border-t border-gray-100">
                <button onClick={() => testMut.mutate(p.id)} disabled={testMut.isPending} title="Testar conexão" className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-brand-600 hover:bg-brand-50 rounded transition-colors">
                  <Play size={11} /> Testar
                </button>
                <button onClick={() => syncMut.mutate(p.id)} disabled={syncMut.isPending && syncMut.variables === p.id} title="Sincronizar usuários" className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-green-600 hover:bg-green-50 rounded transition-colors disabled:opacity-50">
                  {syncMut.isPending && syncMut.variables === p.id ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />} Sincronizar
                </button>
                <button onClick={() => { if (confirm(`Remover "${p.name}" e todos os usuários sincronizados?`)) deleteMut.mutate(p.id); }} className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-red-500 hover:bg-red-50 rounded transition-colors ml-auto">
                  <Trash2 size={11} /> Remover
                </button>
              </div>
            </div>
          );
        })}
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
          <GlpiIntegrationCard />
        </div>
      )}
      <IdentityProvidersSection />
      <RmmIntegrationsSection />
      <LLMProvidersSection isSuperAdmin={isSuperAdmin} />
    </div>
  );
}

// ── DLP Tab ───────────────────────────────────────────────────────────────────

const CATEGORY_LABELS: Record<string, string> = {
  pii_br:     "PII Brasileira (LGPD)",
  credentials:"Credenciais e Secrets",
  infra_mssp: "Infraestrutura MSSP",
  custom:     "Padrões Personalizados",
};

const ACTION_COLORS: Record<string, string> = {
  block: "bg-red-100 text-red-700",
  warn:  "bg-amber-100 text-amber-700",
};

function DLPTab() {
  const qc = useQueryClient();
  const { user, tenant } = useAuth();
  const isSuperAdmin = user?.is_super_admin ?? false;
  const [selectedTenantId, setSelectedTenantId] = useState<string>(
    isSuperAdmin ? "" : (tenant?.id ?? "")
  );
  const [showCustomForm, setShowCustomForm] = useState(false);
  const [customForm, setCustomForm] = useState({
    rule_key: "", rule_name: "", description: "",
    pattern: "", action: "warn" as "block" | "warn",
  });

  const { data: tenants = [] } = useQuery({
    queryKey: ["tenants"],
    queryFn: tenantsApi.list,
    enabled: isSuperAdmin,
  });

  const tid = isSuperAdmin ? selectedTenantId : (tenant?.id ?? "");

  const { data: config, isLoading: loadingConfig } = useQuery({
    queryKey: ["dlp-config", tid],
    queryFn: () => dlpApi.getConfig(isSuperAdmin ? tid : undefined),
    enabled: !!tid,
  });

  const { data: rules = [], isLoading: loadingRules } = useQuery({
    queryKey: ["dlp-rules", tid],
    queryFn: () => dlpApi.listRules(isSuperAdmin ? tid : undefined),
    enabled: !!tid,
  });

  const { data: incidents = [] } = useQuery({
    queryKey: ["dlp-incidents", tid],
    queryFn: () => dlpApi.listIncidents(isSuperAdmin ? tid : undefined, 30),
    enabled: !!tid,
  });

  const configMut = useMutation({
    mutationFn: (data: Parameters<typeof dlpApi.updateConfig>[0]) =>
      dlpApi.updateConfig(data, isSuperAdmin ? tid : undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dlp-config", tid] }),
  });

  const ruleMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { action?: "block" | "warn"; is_enabled?: boolean } }) =>
      dlpApi.updateRule(id, data, isSuperAdmin ? tid : undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dlp-rules", tid] }),
  });

  const createRuleMut = useMutation({
    mutationFn: () => dlpApi.createRule({ ...customForm }, isSuperAdmin ? tid : undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dlp-rules", tid] });
      setShowCustomForm(false);
      setCustomForm({ rule_key: "", rule_name: "", description: "", pattern: "", action: "warn" });
    },
  });

  const deleteRuleMut = useMutation({
    mutationFn: (id: string) => dlpApi.deleteRule(id, isSuperAdmin ? tid : undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dlp-rules", tid] }),
  });

  const categories = Array.from(new Set(rules.map((r: DLPRule) => r.category)));

  return (
    <div className="space-y-6">
      {isSuperAdmin && (
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-gray-700 shrink-0">Tenant:</label>
          <select
            value={selectedTenantId}
            onChange={(e) => setSelectedTenantId(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 min-w-[240px]"
          >
            <option value="">Selecione um tenant...</option>
            {tenants.map((t: { id: string; name: string }) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
      )}

      {!tid ? (
        <div className="text-center py-14 text-gray-400">
          <ShieldAlert size={36} className="mx-auto mb-3 text-gray-200" />
          <p className="text-sm">Selecione um tenant para configurar o DLP.</p>
        </div>
      ) : loadingConfig || loadingRules ? (
        <p className="text-sm text-gray-400 py-6 text-center">Carregando...</p>
      ) : (
        <>
          {/* Configurações Gerais */}
          <div className="bg-gray-50 border border-gray-200 rounded-xl p-5 space-y-4">
            <div className="flex items-center gap-2 mb-1">
              <ShieldAlert size={16} className="text-brand-600" />
              <h3 className="text-sm font-semibold text-gray-800">Configurações Gerais</h3>
            </div>

            {config?.compliance_mode && (
              <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-800">
                <Lock size={12} />
                Modo compliance ativo — DLP não pode ser desativado por admin do tenant.
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <label className="flex items-center justify-between px-3 py-2.5 bg-white border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
                <div>
                  <p className="text-sm font-medium text-gray-800">DLP habilitado</p>
                  <p className="text-xs text-gray-500">Escaneia mensagens antes de enviar ao agente</p>
                </div>
                <button
                  onClick={() => configMut.mutate({ enabled: !config?.enabled })}
                  disabled={configMut.isPending || (config?.compliance_mode && !isSuperAdmin)}
                  className="ml-3 shrink-0"
                >
                  {config?.enabled
                    ? <ToggleRight size={24} className="text-brand-600" />
                    : <ToggleLeft  size={24} className="text-gray-300" />}
                </button>
              </label>

              <label className="flex items-center justify-between px-3 py-2.5 bg-white border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
                <div>
                  <p className="text-sm font-medium text-gray-800">Modo compliance</p>
                  <p className="text-xs text-gray-500">Bloqueia desativação do DLP por admin do tenant</p>
                </div>
                <button
                  onClick={() => configMut.mutate({ compliance_mode: !config?.compliance_mode })}
                  disabled={configMut.isPending || (!isSuperAdmin && config?.compliance_mode)}
                  className="ml-3 shrink-0"
                >
                  {config?.compliance_mode
                    ? <ToggleRight size={24} className="text-amber-500" />
                    : <ToggleLeft  size={24} className="text-gray-300" />}
                </button>
              </label>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm text-gray-600">Alertar após</span>
              <input
                type="number" min={1} max={100}
                defaultValue={config?.incident_threshold_count ?? 5}
                onBlur={(e) => configMut.mutate({ incident_threshold_count: parseInt(e.target.value) || 5 })}
                className="w-16 border border-gray-300 rounded-lg px-2 py-1 text-sm text-center focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <span className="text-sm text-gray-600">incidentes em</span>
              <input
                type="number" min={1} max={168}
                defaultValue={config?.incident_threshold_hours ?? 24}
                onBlur={(e) => configMut.mutate({ incident_threshold_hours: parseInt(e.target.value) || 24 })}
                className="w-16 border border-gray-300 rounded-lg px-2 py-1 text-sm text-center focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <span className="text-sm text-gray-600">horas</span>
            </div>
          </div>

          {/* Regras por categoria */}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Regras de Detecção</p>
            <div className="space-y-4">
              {categories.map((cat) => {
                const catRules = rules.filter((r: DLPRule) => r.category === cat);
                return (
                  <div key={cat} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                    <div className="bg-gray-50 px-4 py-2 border-b border-gray-100">
                      <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                        {CATEGORY_LABELS[cat] ?? cat}
                      </span>
                    </div>
                    <table className="w-full text-sm">
                      <tbody className="divide-y divide-gray-50">
                        {catRules.map((rule: DLPRule) => (
                          <tr key={rule.id} className={`hover:bg-gray-50 ${!rule.is_enabled ? "opacity-50" : ""}`}>
                            <td className="px-4 py-2.5">
                              <p className="font-medium text-gray-800 text-xs">{rule.rule_name}</p>
                              {rule.description && (
                                <p className="text-xs text-gray-400 mt-0.5">{rule.description}</p>
                              )}
                            </td>
                            <td className="px-3 py-2.5 w-32">
                              <select
                                value={rule.action}
                                onChange={(e) => ruleMut.mutate({ id: rule.id, data: { action: e.target.value as "block" | "warn" } })}
                                disabled={ruleMut.isPending}
                                className={`text-xs font-medium px-2 py-0.5 rounded-full border-0 cursor-pointer focus:outline-none focus:ring-1 focus:ring-brand-500 ${ACTION_COLORS[rule.action]}`}
                              >
                                <option value="block">BLOCK</option>
                                <option value="warn">WARN</option>
                              </select>
                            </td>
                            <td className="px-3 py-2.5 w-16 text-right">
                              <button
                                onClick={() => ruleMut.mutate({ id: rule.id, data: { is_enabled: !rule.is_enabled } })}
                                disabled={ruleMut.isPending}
                                title={rule.is_enabled ? "Desativar" : "Ativar"}
                              >
                                {rule.is_enabled
                                  ? <ToggleRight size={18} className="text-brand-600" />
                                  : <ToggleLeft  size={18} className="text-gray-300" />}
                              </button>
                            </td>
                            {!rule.is_builtin && (
                              <td className="px-3 py-2.5 w-10 text-right">
                                <button
                                  onClick={() => { if (confirm(`Remover regra "${rule.rule_name}"?`)) deleteRuleMut.mutate(rule.id); }}
                                  className="text-gray-300 hover:text-red-500 transition-colors"
                                >
                                  <Trash2 size={13} />
                                </button>
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Padrões customizados */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Padrões Personalizados</p>
              <button
                onClick={() => setShowCustomForm((v) => !v)}
                className="flex items-center gap-1.5 text-xs font-medium bg-brand-600 text-white px-3 py-1.5 rounded-lg hover:bg-brand-700"
              >
                <Plus size={12} /> Adicionar padrão
              </button>
            </div>

            {showCustomForm && (
              <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 mb-4 space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">rule_key (único)</label>
                    <input
                      value={customForm.rule_key}
                      onChange={(e) => setCustomForm({ ...customForm, rule_key: e.target.value })}
                      placeholder="ex: matricula_interna"
                      className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Nome</label>
                    <input
                      value={customForm.rule_name}
                      onChange={(e) => setCustomForm({ ...customForm, rule_name: e.target.value })}
                      placeholder="ex: Matrícula Interna"
                      className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Regex (padrão)</label>
                  <input
                    value={customForm.pattern}
                    onChange={(e) => setCustomForm({ ...customForm, pattern: e.target.value })}
                    placeholder="ex: EMP-\d{6}"
                    className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
                <div className="flex items-center gap-3">
                  <label className="text-xs font-medium text-gray-600">Ação:</label>
                  <select
                    value={customForm.action}
                    onChange={(e) => setCustomForm({ ...customForm, action: e.target.value as "block" | "warn" })}
                    className="border border-gray-300 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500"
                  >
                    <option value="block">BLOCK</option>
                    <option value="warn">WARN</option>
                  </select>
                </div>
                {createRuleMut.isError && (
                  <p className="text-xs text-red-600">
                    {(createRuleMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao criar"}
                  </p>
                )}
                <div className="flex gap-2">
                  <button
                    onClick={() => createRuleMut.mutate()}
                    disabled={!customForm.rule_key || !customForm.rule_name || !customForm.pattern || createRuleMut.isPending}
                    className="flex-1 bg-brand-600 text-white text-xs font-medium py-1.5 rounded-lg hover:bg-brand-700 disabled:opacity-50"
                  >
                    {createRuleMut.isPending ? "Criando..." : "Criar regra"}
                  </button>
                  <button onClick={() => setShowCustomForm(false)}
                    className="flex-1 border border-gray-300 text-gray-600 text-xs font-medium py-1.5 rounded-lg hover:bg-gray-50"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Histórico de Incidentes */}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Incidentes Recentes
              <span className="ml-2 text-gray-400 font-normal normal-case">(dado original não é armazenado)</span>
            </p>
            {incidents.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">Nenhum incidente registrado.</p>
            ) : (
              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide border-b border-gray-100">
                    <tr>
                      <th className="text-left px-4 py-2">Tipo</th>
                      <th className="text-left px-4 py-2">Ação</th>
                      <th className="text-left px-4 py-2">Origem</th>
                      <th className="text-left px-4 py-2">IP</th>
                      <th className="text-left px-4 py-2">Data/Hora</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {incidents.map((inc: DLPIncident) => (
                      <tr key={inc.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2.5">
                          <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded text-gray-700">{inc.pii_type}</span>
                        </td>
                        <td className="px-4 py-2.5">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${ACTION_COLORS[inc.action_taken]}`}>
                            {inc.action_taken.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-xs text-gray-500">{inc.source}</td>
                        <td className="px-4 py-2.5 text-xs font-mono text-gray-400">{inc.ip_address ?? "—"}</td>
                        <td className="px-4 py-2.5 text-xs text-gray-500">
                          {new Date(inc.created_at).toLocaleString("pt-BR")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ── Backup Tab ────────────────────────────────────────────────────────────────

const DEST_ICONS_MAP: Record<string, React.ElementType> = {
  local: HardDrive, s3: Cloud, sftp: Server,
};
const JOB_STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-700",
  running: "bg-blue-100 text-blue-700",
  success: "bg-green-100 text-green-700",
  failed:  "bg-red-100 text-red-700",
};

function BackupTab() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [dest, setDest] = useState<"local" | "s3" | "sftp">("local");
  const [form, setForm] = useState<BackupConfigCreate>({
    name: "", destination: "local", retention_count: 7, schedule_cron: null,
  });

  const { data: configs = [], isLoading: lcfg } = useQuery({
    queryKey: ["tenant-backup-configs"],
    queryFn: tenantBackupApi.listConfigs,
  });
  const { data: jobs = [], isLoading: ljobs, refetch: refetchJobs } = useQuery({
    queryKey: ["tenant-backup-jobs"],
    queryFn: tenantBackupApi.listJobs,
    refetchInterval: 5000,
  });

  const createMut = useMutation({
    mutationFn: () => tenantBackupApi.createConfig({ ...form, destination: dest }),
    onSuccess: () => {
      toast.success("Configuração criada");
      qc.invalidateQueries({ queryKey: ["tenant-backup-configs"] });
      setShowForm(false);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Erro ao criar"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => tenantBackupApi.deleteConfig(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenant-backup-configs"] }),
    onError: () => toast.error("Erro ao remover"),
  });

  const runMut = useMutation({
    mutationFn: (id: string) => tenantBackupApi.triggerBackup(id),
    onSuccess: (d) => {
      toast.success(`Backup iniciado (${d.job_id.slice(0, 8)}…)`);
      qc.invalidateQueries({ queryKey: ["tenant-backup-jobs"] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Erro ao iniciar"),
  });

  const restoreMut = useMutation({
    mutationFn: (id: string) => tenantBackupApi.triggerRestore(id),
    onSuccess: () => toast.success("Restore iniciado"),
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Erro ao restaurar"),
  });

  const set = (k: keyof BackupConfigCreate, v: any) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="space-y-6">
      {/* Configurations */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-semibold text-gray-700 flex items-center gap-2">
            <HardDrive size={15} className="text-brand-600" />
            Configurações de Backup
          </p>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="flex items-center gap-1 text-xs bg-brand-600 text-white px-3 py-1.5 rounded-lg hover:bg-brand-700"
          >
            <Plus size={12} /> Nova
          </button>
        </div>

        {showForm && (
          <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3 mb-4">
            <p className="text-xs font-semibold text-gray-600">Nova configuração de backup do tenant</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Nome</label>
                <input value={form.name} onChange={(e) => set("name", e.target.value)}
                  placeholder="Ex: Backup Diário"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Destino</label>
                <select value={dest} onChange={(e) => { setDest(e.target.value as any); set("destination", e.target.value); }}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="local">Local</option>
                  <option value="s3">Amazon S3</option>
                  <option value="sftp">SFTP</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Agendamento (cron)</label>
                <input value={form.schedule_cron ?? ""} onChange={(e) => set("schedule_cron", e.target.value || null)}
                  placeholder="0 2 * * *"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Retenção (cópias)</label>
                <input type="number" min={1} max={90} value={form.retention_count}
                  onChange={(e) => set("retention_count", parseInt(e.target.value) || 7)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
            </div>
            {dest === "local" && (
              <input value={form.local_path ?? ""} onChange={(e) => set("local_path", e.target.value || null)}
                placeholder="Caminho local: /tmp/firemanager_backups"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500" />
            )}
            {dest === "s3" && (
              <div className="grid grid-cols-2 gap-3">
                <input value={form.s3_bucket ?? ""} onChange={(e) => set("s3_bucket", e.target.value)}
                  placeholder="Bucket S3" className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                <input value={form.s3_prefix ?? ""} onChange={(e) => set("s3_prefix", e.target.value)}
                  placeholder="Prefixo/pasta" className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                <input value={form.s3_region ?? ""} onChange={(e) => set("s3_region", e.target.value)}
                  placeholder="Região (us-east-1)" className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                <input value={form.s3_access_key ?? ""} onChange={(e) => set("s3_access_key", e.target.value)}
                  placeholder="Access Key ID" className="border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500" />
                <input type="password" value={form.s3_secret_key ?? ""} onChange={(e) => set("s3_secret_key", e.target.value)}
                  placeholder="Secret Key" className="col-span-2 border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
            )}
            {dest === "sftp" && (
              <div className="grid grid-cols-2 gap-3">
                <input value={form.sftp_host ?? ""} onChange={(e) => set("sftp_host", e.target.value)}
                  placeholder="Host SFTP" className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                <input type="number" value={form.sftp_port ?? 22} onChange={(e) => set("sftp_port", parseInt(e.target.value))}
                  placeholder="Porta" className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                <input value={form.sftp_user ?? ""} onChange={(e) => set("sftp_user", e.target.value)}
                  placeholder="Usuário" className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                <input type="password" value={form.sftp_password ?? ""} onChange={(e) => set("sftp_password", e.target.value)}
                  placeholder="Senha" className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                <input value={form.sftp_path ?? ""} onChange={(e) => set("sftp_path", e.target.value)}
                  placeholder="Caminho remoto: /backups"
                  className="col-span-2 border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
            )}
            <div className="flex gap-2 pt-1">
              <button onClick={() => createMut.mutate()} disabled={!form.name || createMut.isPending}
                className="bg-brand-600 text-white text-sm font-medium px-4 py-1.5 rounded-lg hover:bg-brand-700 disabled:opacity-50">
                {createMut.isPending ? "Criando..." : "Criar"}
              </button>
              <button onClick={() => setShowForm(false)}
                className="border border-gray-300 text-gray-600 text-sm font-medium px-4 py-1.5 rounded-lg hover:bg-gray-50">
                Cancelar
              </button>
            </div>
          </div>
        )}

        {lcfg ? (
          <p className="text-sm text-gray-400">Carregando...</p>
        ) : configs.length === 0 ? (
          <p className="text-sm text-gray-400">Nenhuma configuração. Crie uma para habilitar backups do tenant.</p>
        ) : (
          <div className="space-y-2">
            {configs.map((cfg: BackupConfig) => {
              const DestIcon = DEST_ICONS_MAP[cfg.destination] ?? HardDrive;
              return (
                <div key={cfg.id} className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-3 border border-gray-100">
                  <div className="flex items-center gap-3">
                    <DestIcon size={15} className="text-gray-500 shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-gray-800">{cfg.name}</p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {cfg.destination}
                        {cfg.schedule_cron ? ` · cron: ${cfg.schedule_cron}` : " · manual"}
                        {` · retenção: ${cfg.retention_count}`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={() => runMut.mutate(cfg.id)} disabled={runMut.isPending}
                      className="flex items-center gap-1 text-xs text-brand-600 border border-brand-200 bg-brand-50 hover:bg-brand-100 px-2.5 py-1 rounded font-medium">
                      <Play size={10} /> Executar
                    </button>
                    <button onClick={() => deleteMut.mutate(cfg.id)} disabled={deleteMut.isPending}
                      className="text-gray-400 hover:text-red-500">
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Job History */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-semibold text-gray-700">Histórico de Jobs</p>
          <button onClick={() => refetchJobs()} className="text-gray-400 hover:text-brand-600">
            <RefreshCw size={13} />
          </button>
        </div>
        {ljobs ? (
          <p className="text-sm text-gray-400">Carregando...</p>
        ) : jobs.length === 0 ? (
          <p className="text-sm text-gray-400">Nenhum job executado ainda.</p>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase border-b border-gray-100">
                <tr>
                  <th className="text-left px-4 py-2.5">Status</th>
                  <th className="text-left px-4 py-2.5">Destino</th>
                  <th className="text-left px-4 py-2.5">Arquivo</th>
                  <th className="text-left px-4 py-2.5">Criado em</th>
                  <th className="px-4 py-2.5 w-20" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {jobs.map((job: import("../api/backup").BackupJob) => (
                  <tr key={job.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2.5">
                      <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${JOB_STATUS_COLORS[job.status]}`}>
                        {job.status === "running" ? <Loader2 size={10} className="animate-spin" /> : <Clock size={10} />}
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-600 text-xs">{job.destination}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-gray-500 max-w-[180px] truncate">
                      {job.file_path ? job.file_path.split("/").pop() : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-gray-500">
                      {new Date(job.created_at).toLocaleString("pt-BR")}
                    </td>
                    <td className="px-4 py-2.5">
                      {job.status === "success" && (
                        <button
                          onClick={() => {
                            if (confirm("Restaurar dados deste backup? Os dados existentes serão atualizados.")) {
                              restoreMut.mutate(job.id);
                            }
                          }}
                          disabled={restoreMut.isPending}
                          className="text-xs text-amber-700 border border-amber-200 bg-amber-50 hover:bg-amber-100 px-2 py-0.5 rounded font-medium"
                        >
                          Restaurar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

type Tab = "tenants" | "equipe" | "politica" | "integracoes" | "dlp" | "backup";

export function Organisation() {
  const { user, tenantRole } = useAuth();
  const isSuperAdmin = user?.is_super_admin ?? false;
  const isAdmin = isSuperAdmin || tenantRole === "admin";

  const [searchParams] = useState(() => new URLSearchParams(window.location.search));
  const initialTab = (searchParams.get("tab") as Tab | null) ?? (isSuperAdmin ? "tenants" : "equipe");
  const [tab, setTab] = useState<Tab>(initialTab);

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
    { id: "dlp",          label: "DLP" },
    { id: "backup",       label: "Backup & Restore" },
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
          {tab === "dlp"          && <DLPTab />}
          {tab === "backup"       && <BackupTab />}
        </div>
      </div>
    </PageWrapper>
  );
}
