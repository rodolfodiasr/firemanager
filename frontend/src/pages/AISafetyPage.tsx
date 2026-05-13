import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldCheck, Clock, Users, Trash2, Plus, CheckCircle, XCircle,
  AlertTriangle, Calendar, Eye, Lock,
} from "lucide-react";
import { aiSafetyApi, type ApprovalRequest, type ErasureRequest, type MaintenanceWindow } from "../api/aiSafety";

type Tab = "windows" | "approvals" | "erasure";

// ── helpers ──────────────────────────────────────────────────────────────────
const RISK_COLORS: Record<string, string> = {
  critical: "text-red-400 bg-red-900/40",
  high: "text-orange-400 bg-orange-900/40",
  medium: "text-yellow-400 bg-yellow-900/40",
  low: "text-green-400 bg-green-900/40",
};
const STATUS_BADGE: Record<string, string> = {
  pending_first: "bg-yellow-900/50 text-yellow-300",
  pending_second: "bg-blue-900/50 text-blue-300",
  approved: "bg-green-900/50 text-green-300",
  rejected: "bg-red-900/50 text-red-300",
  expired: "bg-gray-700 text-gray-400",
  pending: "bg-yellow-900/50 text-yellow-300",
  in_progress: "bg-blue-900/50 text-blue-300",
  completed: "bg-green-900/50 text-green-300",
};
const STATUS_LABELS: Record<string, string> = {
  pending_first: "Aguarda 1ª aprovação",
  pending_second: "Aguarda 2ª aprovação",
  approved: "Aprovado",
  rejected: "Rejeitado",
  expired: "Expirado",
  pending: "Pendente",
  in_progress: "Em execução",
  completed: "Concluído",
};
const fmtDt = (dt: string | null | undefined) =>
  dt ? new Date(dt).toLocaleString("pt-BR") : "—";

// ── MaintenanceTab ────────────────────────────────────────────────────────────
function MaintenanceTab() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<{
    name: string; description: string;
    starts_at: string; ends_at: string;
    recurrence: "once" | "weekly" | "monthly";
    block_ai_operations: boolean; block_bulk_jobs: boolean; is_active: boolean;
  }>({
    name: "", description: "",
    starts_at: "", ends_at: "",
    recurrence: "once",
    block_ai_operations: true, block_bulk_jobs: true, is_active: true,
  });

  const { data: windows = [] } = useQuery({ queryKey: ["aisafety-windows"], queryFn: () => aiSafetyApi.listWindows() });
  const { data: activeWindow } = useQuery({ queryKey: ["aisafety-active-window"], queryFn: aiSafetyApi.getActiveWindow });

  const createMut = useMutation({
    mutationFn: (data: typeof form) => aiSafetyApi.createWindow(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["aisafety-windows"] }); setShowForm(false); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => aiSafetyApi.deleteWindow(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["aisafety-windows"] }),
  });
  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      aiSafetyApi.updateWindow(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["aisafety-windows"] }),
  });

  return (
    <div>
      {activeWindow && (
        <div className="bg-orange-900/40 border border-orange-700 rounded-xl p-4 mb-4 flex items-center gap-3">
          <AlertTriangle size={20} className="text-orange-400" />
          <div>
            <div className="text-orange-300 font-semibold">Janela de manutenção ativa: {activeWindow.name}</div>
            <div className="text-orange-400 text-sm">
              Operações IA bloqueadas até {fmtDt(activeWindow.ends_at)}
            </div>
          </div>
        </div>
      )}
      <div className="flex justify-end mb-4">
        <button onClick={() => setShowForm(true)}
          className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
          <Plus size={16} /> Nova Janela
        </button>
      </div>
      {showForm && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-5 mb-4">
          <h3 className="text-white font-semibold mb-4">Nova Janela de Manutenção</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="col-span-2">
              <label className="text-xs text-gray-400 block mb-1">Nome</label>
              <input value={form.name} onChange={e => setForm({...form, name: e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Início</label>
              <input type="datetime-local" value={form.starts_at} onChange={e => setForm({...form, starts_at: e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Fim</label>
              <input type="datetime-local" value={form.ends_at} onChange={e => setForm({...form, ends_at: e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Recorrência</label>
              <select value={form.recurrence} onChange={e => setForm({...form, recurrence: e.target.value as "once" | "weekly" | "monthly"})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm">
                <option value="once">Uma vez</option>
                <option value="weekly">Semanal</option>
                <option value="monthly">Mensal</option>
              </select>
            </div>
          </div>
          <div className="flex items-center gap-4 mb-4">
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input type="checkbox" checked={form.block_ai_operations}
                onChange={e => setForm({...form, block_ai_operations: e.target.checked})} className="accent-brand-500" />
              Bloquear operações IA
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input type="checkbox" checked={form.block_bulk_jobs}
                onChange={e => setForm({...form, block_bulk_jobs: e.target.checked})} className="accent-brand-500" />
              Bloquear bulk jobs
            </label>
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-white px-4 py-2 text-sm">Cancelar</button>
            <button onClick={() => createMut.mutate(form)} disabled={!form.name || !form.starts_at || createMut.isPending}
              className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
              {createMut.isPending ? "Criando..." : "Criar"}
            </button>
          </div>
        </div>
      )}
      <div className="space-y-3">
        {windows.map(w => {
          const now = new Date();
          const start = new Date(w.starts_at);
          const end = new Date(w.ends_at);
          const isNow = w.is_active && start <= now && end >= now;
          return (
            <div key={w.id} className={`bg-gray-800 border rounded-xl p-4 flex items-center justify-between ${isNow ? "border-orange-700" : "border-gray-700"}`}>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-white font-medium">{w.name}</span>
                  {isNow && <span className="text-xs bg-orange-600 text-white px-2 py-0.5 rounded">ATIVA AGORA</span>}
                </div>
                <div className="text-sm text-gray-400 mt-1">
                  <Calendar size={12} className="inline mr-1" />
                  {fmtDt(w.starts_at)} → {fmtDt(w.ends_at)}
                </div>
                <div className="flex gap-3 mt-1 text-xs text-gray-500">
                  {w.block_ai_operations && <span className="flex items-center gap-1"><Lock size={10} />IA bloqueada</span>}
                  {w.block_bulk_jobs && <span className="flex items-center gap-1"><Lock size={10} />Bulk bloqueado</span>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => toggleMut.mutate({ id: w.id, is_active: !w.is_active })}
                  className={`text-xs px-2 py-1 rounded ${w.is_active ? "bg-green-900/50 text-green-300 hover:bg-green-900" : "bg-gray-700 text-gray-400 hover:bg-gray-600"}`}>
                  {w.is_active ? "Ativa" : "Inativa"}
                </button>
                <button onClick={() => { if (confirm("Excluir janela?")) deleteMut.mutate(w.id); }}
                  className="text-red-400 hover:text-red-300"><Trash2 size={14} /></button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── ApprovalsTab ──────────────────────────────────────────────────────────────
function ApprovalsTab() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<string>("");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", risk_level: "high", requires_two_approvals: true });
  const [rejectId, setRejectId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const { data: items = [] } = useQuery({
    queryKey: ["aisafety-approvals", filter],
    queryFn: () => aiSafetyApi.listApprovals(filter || undefined),
  });

  const createMut = useMutation({
    mutationFn: (data: typeof form) => aiSafetyApi.createApproval(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["aisafety-approvals"] }); setShowCreate(false); },
  });
  const approveMut = useMutation({
    mutationFn: (id: string) => aiSafetyApi.approve(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["aisafety-approvals"] }),
  });
  const rejectMut = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => aiSafetyApi.reject(id, reason),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["aisafety-approvals"] }); setRejectId(null); setRejectReason(""); },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-3">
        <div className="flex gap-2">
          {["", "pending_first", "pending_second", "approved", "rejected"].map(s => (
            <button key={s} onClick={() => setFilter(s)}
              className={`text-xs px-3 py-1.5 rounded-lg ${filter === s ? "bg-brand-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>
              {s === "" ? "Todos" : STATUS_LABELS[s]}
            </button>
          ))}
        </div>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
          <Plus size={16} /> Nova Solicitação
        </button>
      </div>

      {showCreate && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-5 mb-4">
          <h3 className="text-white font-semibold mb-4">Nova Solicitação de Aprovação (Four-eyes)</h3>
          <div className="space-y-3 mb-4">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Título da operação</label>
              <input value={form.title} onChange={e => setForm({...form, title: e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Descrição / justificativa</label>
              <textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})} rows={2}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400 block mb-1">Nível de risco</label>
                <select value={form.risk_level} onChange={e => setForm({...form, risk_level: e.target.value})}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm">
                  <option value="critical">Crítico</option>
                  <option value="high">Alto</option>
                  <option value="medium">Médio</option>
                </select>
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer mb-2">
                  <input type="checkbox" checked={form.requires_two_approvals}
                    onChange={e => setForm({...form, requires_two_approvals: e.target.checked})} className="accent-brand-500" />
                  Exigir 2 aprovadores (four-eyes)
                </label>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-white px-4 py-2 text-sm">Cancelar</button>
            <button onClick={() => createMut.mutate(form)} disabled={!form.title || createMut.isPending}
              className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
              {createMut.isPending ? "Criando..." : "Criar"}
            </button>
          </div>
        </div>
      )}

      {rejectId && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-xl p-5 w-full max-w-md border border-gray-700">
            <h3 className="text-white font-semibold mb-3">Rejeitar solicitação</h3>
            <textarea value={rejectReason} onChange={e => setRejectReason(e.target.value)} rows={3}
              placeholder="Motivo da rejeição..."
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm mb-4" />
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
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${RISK_COLORS[req.risk_level] ?? ""}`}>{req.risk_level}</span>
                  <span className="text-white font-medium text-sm">{req.title}</span>
                </div>
                {req.description && <p className="text-gray-400 text-xs">{req.description}</p>}
              </div>
              <span className={`text-xs px-2 py-0.5 rounded ${STATUS_BADGE[req.status] ?? "bg-gray-700 text-gray-400"}`}>
                {STATUS_LABELS[req.status]}
              </span>
            </div>
            <div className="flex items-center gap-4 text-xs text-gray-500 mb-3">
              <span>Criado: {fmtDt(req.created_at)}</span>
              {req.expires_at && <span>Expira: {fmtDt(req.expires_at)}</span>}
              {req.requires_two_approvals && <span className="flex items-center gap-1"><Users size={10} />Four-eyes</span>}
            </div>
            {(req.status === "pending_first" || req.status === "pending_second") && (
              <div className="flex gap-2">
                <button onClick={() => approveMut.mutate(req.id)} disabled={approveMut.isPending}
                  className="flex items-center gap-1 bg-green-800 hover:bg-green-700 text-white px-3 py-1.5 rounded-lg text-xs">
                  <CheckCircle size={12} /> Aprovar
                </button>
                <button onClick={() => setRejectId(req.id)}
                  className="flex items-center gap-1 bg-red-800 hover:bg-red-700 text-white px-3 py-1.5 rounded-lg text-xs">
                  <XCircle size={12} /> Rejeitar
                </button>
              </div>
            )}
            {req.rejection_reason && (
              <p className="text-red-400 text-xs mt-2">Motivo: {req.rejection_reason}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── ErasureTab ────────────────────────────────────────────────────────────────
function ErasureTab() {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ target_user_email: "", reason: "", legal_basis: "Art. 18 LGPD — Direito à eliminação" });

  const { data: items = [] } = useQuery({ queryKey: ["aisafety-erasure"], queryFn: () => aiSafetyApi.listErasure() });
  const createMut = useMutation({
    mutationFn: (data: typeof form) => aiSafetyApi.createErasure(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["aisafety-erasure"] }); setShowCreate(false); },
  });
  const approveMut = useMutation({
    mutationFn: (id: string) => aiSafetyApi.approveErasure(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["aisafety-erasure"] }),
  });
  const executeMut = useMutation({
    mutationFn: (id: string) => aiSafetyApi.executeErasure(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["aisafety-erasure"] }),
  });

  return (
    <div>
      <div className="bg-blue-900/30 border border-blue-700 rounded-xl p-4 mb-4 flex items-start gap-3">
        <ShieldCheck size={18} className="text-blue-400 mt-0.5 shrink-0" />
        <div className="text-sm text-blue-200">
          <strong>Direito à Eliminação (LGPD Art. 18)</strong> — Solicite a remoção/anonimização de dados pessoais.
          As solicitações requerem aprovação e são executadas com rastreamento completo.
        </div>
      </div>
      <div className="flex justify-end mb-4">
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
          <Plus size={16} /> Nova Solicitação
        </button>
      </div>
      {showCreate && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-5 mb-4">
          <h3 className="text-white font-semibold mb-4">Solicitação de Eliminação LGPD</h3>
          <div className="space-y-3 mb-4">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Email do titular dos dados</label>
              <input value={form.target_user_email} onChange={e => setForm({...form, target_user_email: e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Motivo</label>
              <textarea value={form.reason} onChange={e => setForm({...form, reason: e.target.value})} rows={2}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Base legal</label>
              <input value={form.legal_basis} onChange={e => setForm({...form, legal_basis: e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-white px-4 py-2 text-sm">Cancelar</button>
            <button onClick={() => createMut.mutate(form)}
              disabled={!form.target_user_email || createMut.isPending}
              className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
              {createMut.isPending ? "Criando..." : "Solicitar"}
            </button>
          </div>
        </div>
      )}
      <div className="space-y-3">
        {items.map(req => (
          <div key={req.id} className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="text-white font-medium text-sm">{req.target_user_email}</div>
                {req.reason && <p className="text-gray-400 text-xs mt-1">{req.reason}</p>}
                {req.legal_basis && <p className="text-blue-400 text-xs mt-1">{req.legal_basis}</p>}
              </div>
              <span className={`text-xs px-2 py-0.5 rounded ${STATUS_BADGE[req.status] ?? "bg-gray-700 text-gray-400"}`}>
                {STATUS_LABELS[req.status]}
              </span>
            </div>
            <div className="text-xs text-gray-500 mb-3">
              Criado: {fmtDt(req.created_at)}
              {req.completed_at && ` · Concluído: ${fmtDt(req.completed_at)}`}
            </div>
            {req.audit_summary && (
              <div className="text-xs text-green-400 bg-green-900/20 rounded p-2 mb-2">
                Tabelas afetadas: {(req.affected_tables ?? []).join(", ")}
              </div>
            )}
            <div className="flex gap-2">
              {req.status === "pending" && (
                <button onClick={() => approveMut.mutate(req.id)} disabled={approveMut.isPending}
                  className="flex items-center gap-1 bg-green-800 hover:bg-green-700 text-white px-3 py-1.5 rounded-lg text-xs">
                  <CheckCircle size={12} /> Aprovar
                </button>
              )}
              {req.status === "in_progress" && (
                <button onClick={() => { if (confirm(`Executar eliminação para ${req.target_user_email}? Esta ação não pode ser desfeita.`)) executeMut.mutate(req.id); }}
                  disabled={executeMut.isPending}
                  className="flex items-center gap-1 bg-red-800 hover:bg-red-700 text-white px-3 py-1.5 rounded-lg text-xs">
                  <Trash2 size={12} /> {executeMut.isPending ? "Executando..." : "Executar Eliminação"}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function AISafetyPage() {
  const [tab, setTab] = useState<Tab>("windows");

  const TABS: { id: Tab; label: string; icon: JSX.Element }[] = [
    { id: "windows", label: "Janelas de Manutenção", icon: <Clock size={16} /> },
    { id: "approvals", label: "Aprovação Four-Eyes", icon: <Users size={16} /> },
    { id: "erasure", label: "Eliminação LGPD", icon: <Trash2 size={16} /> },
  ];

  return (
    <main className="flex-1 overflow-auto bg-gray-950 p-6">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-1">IA Safety & Governança</h1>
        <p className="text-gray-400 text-sm mb-6">
          Janelas de manutenção, aprovação dupla (four-eyes) para operações críticas e gestão de direito à eliminação (LGPD).
        </p>

        <div className="flex gap-1 mb-6 bg-gray-800 rounded-xl p-1">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors flex-1 justify-center ${tab === t.id ? "bg-brand-600 text-white" : "text-gray-400 hover:text-white"}`}>
              {t.icon}{t.label}
            </button>
          ))}
        </div>

        {tab === "windows" && <MaintenanceTab />}
        {tab === "approvals" && <ApprovalsTab />}
        {tab === "erasure" && <ErasureTab />}
      </div>
    </main>
  );
}
