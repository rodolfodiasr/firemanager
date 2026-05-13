import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Users, BookOpen, BarChart3, Plus, CheckCircle, XCircle,
  Search, ShieldCheck, Clock, Download,
} from "lucide-react";
import {
  selfservicePortalApi, type AccessRequest, type AdReportRow, type CatalogItem,
} from "../api/selfservicePortal";
import { useAuthStore } from "../store/authStore";

type Tab = "catalog" | "requests" | "reports";

// ── helpers ──────────────────────────────────────────────────────────────────
const CATEGORY_LABELS: Record<string, string> = {
  network: "Rede", server: "Servidor", database: "Banco de Dados",
  application: "Aplicação", security: "Segurança", general: "Geral",
};
const CATEGORY_COLORS: Record<string, string> = {
  network: "bg-blue-900/50 text-blue-300",
  server: "bg-purple-900/50 text-purple-300",
  database: "bg-orange-900/50 text-orange-300",
  application: "bg-green-900/50 text-green-300",
  security: "bg-red-900/50 text-red-300",
  general: "bg-gray-700 text-gray-300",
};
const fmtDt = (dt: string | null | undefined) =>
  dt ? new Date(dt).toLocaleDateString("pt-BR") : "—";
const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-900/50 text-yellow-300",
  approved: "bg-green-900/50 text-green-300",
  rejected: "bg-red-900/50 text-red-300",
};

// ── CatalogTab ────────────────────────────────────────────────────────────────
function CatalogTab({ isAdmin }: { isAdmin: boolean }) {
  const qc = useQueryClient();
  const user = useAuthStore(s => s.user);
  const [filterCat, setFilterCat] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [requestItem, setRequestItem] = useState<CatalogItem | null>(null);
  const [requestForm, setRequestForm] = useState({ requester_email: user?.email ?? "", requester_name: "", business_justification: "" });
  const [newItem, setNewItem] = useState({ name: "", description: "", category: "general", ad_group: "", approval_required: true, icon: "" });

  const { data: items = [] } = useQuery({
    queryKey: ["ss-catalog", filterCat],
    queryFn: () => selfservicePortalApi.listCatalog(filterCat || undefined),
  });

  const createMut = useMutation({
    mutationFn: (data: typeof newItem) => selfservicePortalApi.createCatalogItem(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ss-catalog"] }); setShowCreate(false); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => selfservicePortalApi.deleteCatalogItem(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ss-catalog"] }),
  });
  const requestMut = useMutation({
    mutationFn: () => selfservicePortalApi.submitRequest({
      catalog_item_id: requestItem!.id,
      requester_email: requestForm.requester_email,
      requester_name: requestForm.requester_name,
      business_justification: requestForm.business_justification,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ss-requests"] }); setRequestItem(null); },
  });

  const categories = Array.from(new Set(items.map(i => i.category)));

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-3">
        <div className="flex gap-2 flex-wrap">
          <button onClick={() => setFilterCat("")}
            className={`text-xs px-3 py-1.5 rounded-lg ${filterCat === "" ? "bg-brand-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>
            Todos
          </button>
          {categories.map(c => (
            <button key={c} onClick={() => setFilterCat(c)}
              className={`text-xs px-3 py-1.5 rounded-lg ${filterCat === c ? "bg-brand-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>
              {CATEGORY_LABELS[c] ?? c}
            </button>
          ))}
        </div>
        {isAdmin && (
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm shrink-0">
            <Plus size={16} /> Novo Item
          </button>
        )}
      </div>

      {showCreate && isAdmin && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-5 mb-4">
          <h3 className="text-white font-semibold mb-4">Novo Item do Catálogo</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="col-span-2">
              <label className="text-xs text-gray-400 block mb-1">Nome</label>
              <input value={newItem.name} onChange={e => setNewItem({...newItem, name: e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Categoria</label>
              <select value={newItem.category} onChange={e => setNewItem({...newItem, category: e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm">
                {Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Grupo AD</label>
              <input value={newItem.ad_group} onChange={e => setNewItem({...newItem, ad_group: e.target.value})}
                placeholder="GRP-TI-VPN-Usuarios"
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-gray-400 block mb-1">Descrição</label>
              <textarea value={newItem.description} onChange={e => setNewItem({...newItem, description: e.target.value})} rows={2}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div className="flex items-center">
              <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                <input type="checkbox" checked={newItem.approval_required}
                  onChange={e => setNewItem({...newItem, approval_required: e.target.checked})} className="accent-brand-500" />
                Requer aprovação
              </label>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-white px-4 py-2 text-sm">Cancelar</button>
            <button onClick={() => createMut.mutate(newItem)} disabled={!newItem.name || createMut.isPending}
              className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
              {createMut.isPending ? "Criando..." : "Criar"}
            </button>
          </div>
        </div>
      )}

      {requestItem && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-xl p-6 w-full max-w-md border border-gray-700">
            <h3 className="text-white font-semibold mb-1">Solicitar acesso</h3>
            <p className="text-gray-400 text-sm mb-4">{requestItem.name}</p>
            <div className="space-y-3 mb-4">
              <div>
                <label className="text-xs text-gray-400 block mb-1">Seu email</label>
                <input value={requestForm.requester_email}
                  onChange={e => setRequestForm({...requestForm, requester_email: e.target.value})}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">Justificativa de negócio</label>
                <textarea value={requestForm.business_justification}
                  onChange={e => setRequestForm({...requestForm, business_justification: e.target.value})} rows={3}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setRequestItem(null)} className="text-gray-400 hover:text-white px-4 py-2 text-sm">Cancelar</button>
              <button onClick={() => requestMut.mutate()} disabled={!requestForm.requester_email || requestMut.isPending}
                className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
                {requestMut.isPending ? "Enviando..." : "Solicitar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {items.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <BookOpen size={36} className="mx-auto mb-3 opacity-40" />
          <p>Catálogo vazio.{isAdmin && " Adicione itens para que os usuários solicitem acesso."}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map(item => (
          <div key={item.id} className="bg-gray-800 border border-gray-700 rounded-xl p-5 flex flex-col">
            <div className="flex items-start justify-between mb-2">
              <span className={`text-xs px-2 py-0.5 rounded ${CATEGORY_COLORS[item.category] ?? CATEGORY_COLORS.general}`}>
                {CATEGORY_LABELS[item.category] ?? item.category}
              </span>
              {item.approval_required
                ? <span className="text-xs text-yellow-400 flex items-center gap-1"><Clock size={10} />Aprovação</span>
                : <span className="text-xs text-green-400 flex items-center gap-1"><CheckCircle size={10} />Auto</span>}
            </div>
            <h3 className="text-white font-semibold mb-1 flex-1">{item.name}</h3>
            {item.description && <p className="text-gray-400 text-xs mb-3 line-clamp-2">{item.description}</p>}
            {item.ad_group && <p className="text-xs text-gray-500 font-mono mb-3">{item.ad_group}</p>}
            <div className="flex gap-2 mt-auto">
              <button onClick={() => setRequestItem(item)}
                className="flex-1 bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg text-sm">
                Solicitar acesso
              </button>
              {isAdmin && (
                <button onClick={() => { if (confirm("Excluir item?")) deleteMut.mutate(item.id); }}
                  className="text-red-400 hover:text-red-300 px-2 py-1.5"><XCircle size={14} /></button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── RequestsTab ───────────────────────────────────────────────────────────────
function RequestsTab({ isAdmin }: { isAdmin: boolean }) {
  const qc = useQueryClient();
  const [filter, setFilter] = useState("");
  const [rejectId, setRejectId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const { data: items = [] } = useQuery({
    queryKey: ["ss-requests", filter],
    queryFn: () => selfservicePortalApi.listAccessRequests(filter || undefined),
  });
  const approveMut = useMutation({
    mutationFn: (id: string) => selfservicePortalApi.approveRequest(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ss-requests"] }),
  });
  const rejectMut = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      selfservicePortalApi.rejectRequest(id, reason),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ss-requests"] }); setRejectId(null); setRejectReason(""); },
  });

  return (
    <div>
      <div className="flex gap-2 mb-4">
        {["", "pending", "approved", "rejected"].map(s => (
          <button key={s} onClick={() => setFilter(s)}
            className={`text-xs px-3 py-1.5 rounded-lg ${filter === s ? "bg-brand-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>
            {s === "" ? "Todas" : s === "pending" ? "Pendentes" : s === "approved" ? "Aprovadas" : "Rejeitadas"}
          </button>
        ))}
      </div>

      {rejectId && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-xl p-5 w-full max-w-md border border-gray-700">
            <h3 className="text-white font-semibold mb-3">Rejeitar solicitação</h3>
            <textarea value={rejectReason} onChange={e => setRejectReason(e.target.value)} rows={3}
              placeholder="Motivo..." className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm mb-4" />
            <div className="flex justify-end gap-2">
              <button onClick={() => setRejectId(null)} className="text-gray-400 hover:text-white px-4 py-2 text-sm">Cancelar</button>
              <button onClick={() => rejectMut.mutate({ id: rejectId, reason: rejectReason })}
                disabled={!rejectReason || rejectMut.isPending}
                className="bg-red-700 hover:bg-red-800 text-white px-4 py-2 rounded-lg text-sm">Rejeitar</button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {items.map(req => (
          <div key={req.id} className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="text-white font-medium text-sm">{req.item_name}</div>
                <div className="text-gray-400 text-xs mt-0.5">
                  {req.requester_email} · {fmtDt(req.created_at)}
                </div>
                {req.business_justification && (
                  <p className="text-gray-400 text-xs mt-1 italic">"{req.business_justification}"</p>
                )}
              </div>
              <span className={`text-xs px-2 py-0.5 rounded ${STATUS_COLORS[req.status] ?? "bg-gray-700 text-gray-400"}`}>
                {req.status === "pending" ? "Pendente" : req.status === "approved" ? "Aprovada" : "Rejeitada"}
              </span>
            </div>
            {req.status === "pending" && isAdmin && (
              <div className="flex gap-2 mt-2">
                <button onClick={() => approveMut.mutate(req.id)} disabled={approveMut.isPending}
                  className="flex items-center gap-1 bg-green-800 hover:bg-green-700 text-white px-3 py-1.5 rounded-lg text-xs">
                  <CheckCircle size={12} /> Aprovar e Provisionar
                </button>
                <button onClick={() => setRejectId(req.id)}
                  className="flex items-center gap-1 bg-red-800 hover:bg-red-700 text-white px-3 py-1.5 rounded-lg text-xs">
                  <XCircle size={12} /> Rejeitar
                </button>
              </div>
            )}
            {req.rejection_reason && <p className="text-red-400 text-xs mt-2">Motivo: {req.rejection_reason}</p>}
            {req.provisioned_at && <p className="text-green-400 text-xs mt-2">Provisionado em {fmtDt(req.provisioned_at)}</p>}
          </div>
        ))}
        {items.length === 0 && <p className="text-gray-400 text-center py-8">Nenhuma solicitação encontrada.</p>}
      </div>
    </div>
  );
}

// ── ReportsTab ────────────────────────────────────────────────────────────────
function ReportsTab() {
  const [activeReport, setActiveReport] = useState<string | null>(null);
  const [groupSearch, setGroupSearch] = useState("");
  const [maxAge, setMaxAge] = useState(90);
  const [inactiveDays, setInactiveDays] = useState(60);

  const expiredQ = useQuery({
    queryKey: ["ss-report-expired", maxAge],
    queryFn: () => selfservicePortalApi.reportExpiredPasswords(maxAge),
    enabled: activeReport === "expired",
  });
  const inactiveQ = useQuery({
    queryKey: ["ss-report-inactive", inactiveDays],
    queryFn: () => selfservicePortalApi.reportInactiveAccounts(inactiveDays),
    enabled: activeReport === "inactive",
  });
  const mfaQ = useQuery({
    queryKey: ["ss-report-mfa"],
    queryFn: selfservicePortalApi.reportAdminsWithoutMfa,
    enabled: activeReport === "mfa",
  });
  const groupQ = useQuery({
    queryKey: ["ss-report-group", groupSearch],
    queryFn: () => selfservicePortalApi.reportGroupMembers(groupSearch),
    enabled: activeReport === "group" && groupSearch.length > 1,
  });

  function AdTable({ rows, cols }: { rows: AdReportRow[]; cols: { key: keyof AdReportRow; label: string }[] }) {
    return (
      <div className="overflow-x-auto mt-4">
        <table className="w-full text-sm">
          <thead><tr className="text-gray-400 border-b border-gray-700">
            {cols.map(c => <th key={c.key} className="text-left py-2 px-3 text-xs font-semibold uppercase">{c.label}</th>)}
          </tr></thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50">
                {cols.map(c => (
                  <td key={c.key} className="py-2 px-3 text-gray-200">
                    {c.key === "is_enabled"
                      ? row[c.key] ? <CheckCircle size={14} className="text-green-400" /> : <XCircle size={14} className="text-red-400" />
                      : c.key === "last_logon" || c.key === "password_last_set"
                        ? fmtDt(row[c.key] as string)
                        : String(row[c.key] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="text-gray-400 text-center py-4 text-sm">Nenhum resultado.</p>}
      </div>
    );
  }

  const REPORTS = [
    { id: "expired", label: "Senhas Expiradas", icon: <Clock size={18} className="text-yellow-400" /> },
    { id: "inactive", label: "Contas Inativas", icon: <Users size={18} className="text-gray-400" /> },
    { id: "mfa", label: "Admins sem MFA", icon: <ShieldCheck size={18} className="text-red-400" /> },
    { id: "group", label: "Membros de Grupo", icon: <Search size={18} className="text-blue-400" /> },
  ];

  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {REPORTS.map(r => (
          <button key={r.id} onClick={() => setActiveReport(activeReport === r.id ? null : r.id)}
            className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition-colors ${activeReport === r.id ? "bg-brand-900/50 border-brand-500" : "bg-gray-800 border-gray-700 hover:border-gray-600"}`}>
            {r.icon}
            <span className="text-sm text-white text-center">{r.label}</span>
          </button>
        ))}
      </div>

      {activeReport === "expired" && (
        <div className="bg-gray-800 rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <label className="text-sm text-gray-300">Senhas não alteradas há mais de</label>
            <input type="number" value={maxAge} onChange={e => setMaxAge(+e.target.value)} min={1} max={365}
              className="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-sm" />
            <span className="text-sm text-gray-300">dias</span>
          </div>
          {expiredQ.isLoading ? <p className="text-gray-400 py-4">Carregando...</p> : (
            <AdTable rows={expiredQ.data ?? []} cols={[
              { key: "display_name", label: "Nome" },
              { key: "sam_account_name", label: "Login" },
              { key: "email", label: "Email" },
              { key: "password_last_set", label: "Última alteração" },
              { key: "days_since_change", label: "Dias" },
              { key: "is_enabled", label: "Ativa" },
            ]} />
          )}
        </div>
      )}

      {activeReport === "inactive" && (
        <div className="bg-gray-800 rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <label className="text-sm text-gray-300">Último login há mais de</label>
            <input type="number" value={inactiveDays} onChange={e => setInactiveDays(+e.target.value)} min={1} max={365}
              className="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-sm" />
            <span className="text-sm text-gray-300">dias</span>
          </div>
          {inactiveQ.isLoading ? <p className="text-gray-400 py-4">Carregando...</p> : (
            <AdTable rows={inactiveQ.data ?? []} cols={[
              { key: "display_name", label: "Nome" },
              { key: "sam_account_name", label: "Login" },
              { key: "email", label: "Email" },
              { key: "last_logon", label: "Último login" },
              { key: "days_inactive", label: "Dias inativo" },
            ]} />
          )}
        </div>
      )}

      {activeReport === "mfa" && (
        <div className="bg-gray-800 rounded-xl p-4">
          <p className="text-sm text-gray-400 mb-2">Administradores (grupos *Admin*) sem MFA habilitado</p>
          {mfaQ.isLoading ? <p className="text-gray-400 py-4">Carregando...</p> : (
            <AdTable rows={mfaQ.data ?? []} cols={[
              { key: "display_name", label: "Nome" },
              { key: "sam_account_name", label: "Login" },
              { key: "email", label: "Email" },
              { key: "last_logon", label: "Último login" },
              { key: "is_enabled", label: "Ativa" },
            ]} />
          )}
        </div>
      )}

      {activeReport === "group" && (
        <div className="bg-gray-800 rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <label className="text-sm text-gray-300">Nome do grupo:</label>
            <input value={groupSearch} onChange={e => setGroupSearch(e.target.value)}
              placeholder="Domain Admins"
              className="flex-1 bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm" />
          </div>
          {groupQ.isLoading ? <p className="text-gray-400 py-4">Buscando...</p> : (
            <AdTable rows={groupQ.data ?? []} cols={[
              { key: "display_name", label: "Nome" },
              { key: "sam_account_name", label: "Login" },
              { key: "email", label: "Email" },
              { key: "job_title", label: "Cargo" },
              { key: "is_enabled", label: "Ativa" },
            ]} />
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function SelfServicePortalPage() {
  const [tab, setTab] = useState<Tab>("catalog");
  const user = useAuthStore(s => s.user);
  const isAdmin = user?.role === "admin";

  const TABS: { id: Tab; label: string; icon: JSX.Element }[] = [
    { id: "catalog", label: "Catálogo de Acesso", icon: <BookOpen size={16} /> },
    { id: "requests", label: "Solicitações", icon: <ClockIcon size={16} /> },
    { id: "reports", label: "Relatórios AD", icon: <BarChart3 size={16} /> },
  ];

  return (
    <main className="flex-1 overflow-auto bg-gray-950 p-6">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-1">Self-Service de Identidade</h1>
        <p className="text-gray-400 text-sm mb-6">
          Catálogo de acesso visual, solicitações de acesso e relatórios AD pré-prontos.
        </p>

        <div className="flex gap-1 mb-6 bg-gray-800 rounded-xl p-1">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors flex-1 justify-center ${tab === t.id ? "bg-brand-600 text-white" : "text-gray-400 hover:text-white"}`}>
              {t.icon}{t.label}
            </button>
          ))}
        </div>

        {tab === "catalog" && <CatalogTab isAdmin={isAdmin} />}
        {tab === "requests" && <RequestsTab isAdmin={isAdmin} />}
        {tab === "reports" && <ReportsTab />}
      </div>
    </main>
  );
}

// inline icon helper (Clock was already imported)
function ClockIcon({ size }: { size: number }) {
  return <Clock size={size} />;
}
