import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Database,
  Info,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  ShieldAlert,
  Trash2,
  Wifi,
  WifiOff,
  X,
  XCircle,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { databaseApi, type ConnectorPayload } from "../api/database";
import type { AuditReport, AuditSummary, DatabaseConnector, DbFinding, DbType } from "../types/database";

// ── Constants ─────────────────────────────────────────────────────────────────

const DB_TYPES = [
  { value: "postgresql", label: "PostgreSQL",  port: 5432 },
  { value: "mysql",      label: "MySQL",        port: 3306 },
  { value: "mariadb",    label: "MariaDB",      port: 3306 },
  { value: "sqlserver",  label: "SQL Server",   port: 1433 },
  { value: "oracle",     label: "Oracle",       port: 1521 },
];

const DB_COLORS: Record<string, string> = {
  postgresql: "bg-blue-100 text-blue-700",
  mysql:      "bg-orange-100 text-orange-700",
  mariadb:    "bg-orange-100 text-orange-700",
  sqlserver:  "bg-red-100 text-red-700",
  oracle:     "bg-red-100 text-red-800",
};

const SEVERITY_STYLE: Record<string, string> = {
  high:   "bg-red-100 text-red-700",
  medium: "bg-yellow-100 text-yellow-700",
  low:    "bg-gray-100 text-gray-600",
};

const FINDING_LABELS: Record<string, string> = {
  excessive_privilege: "Privilégio excessivo",
  idle_account:        "Conta ociosa",
  no_password_expiry:  "Senha sem expiração",
  expired_password:    "Senha expirada",
  never_logged_in:     "Nunca acessou",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function dbLabel(type: string) {
  return DB_TYPES.find((t) => t.value === type)?.label ?? type;
}

// ── Connector modal ───────────────────────────────────────────────────────────

interface ConnectorModalProps {
  initial?: DatabaseConnector;
  onClose: () => void;
  onSaved: () => void;
}

function ConnectorModal({ initial, onClose, onSaved }: ConnectorModalProps) {
  const [name, setName]         = useState(initial?.name ?? "");
  const [desc, setDesc]         = useState(initial?.description ?? "");
  const [dbType, setDbType]     = useState(initial?.db_type ?? "postgresql");
  const [host, setHost]         = useState(initial?.host ?? "");
  const [port, setPort]         = useState<number>(initial?.port ?? 5432);
  const [dbName, setDbName]     = useState(initial?.database_name ?? "");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [ssl, setSsl]           = useState(false);

  function handleTypeChange(t: DbType) {
    setDbType(t);
    const def = DB_TYPES.find((d) => d.value === t);
    if (def && !initial) setPort(def.port);
  }

  const qc = useQueryClient();
  const mut = useMutation({
    mutationFn: (payload: ConnectorPayload) =>
      initial ? databaseApi.update(initial.id, payload) : databaseApi.create(payload),
    onSuccess: () => {
      toast.success(initial ? "Conector atualizado" : "Conector criado");
      qc.invalidateQueries({ queryKey: ["db-connectors"] });
      onSaved();
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Falha ao salvar"),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const creds: ConnectorPayload["credentials"] = { username, password, ssl };
    mut.mutate({ name, description: desc || undefined, db_type: dbType, host, port, database_name: dbName, credentials: creds });
  }

  const inputCls = "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500";
  const labelCls = "block text-xs font-medium text-gray-600 mb-1";

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-base font-semibold text-gray-800">
            {initial ? "Editar Conector" : "Novo Conector de Banco"}
          </h2>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="px-6 py-4 space-y-3 max-h-[70vh] overflow-y-auto">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className={labelCls}>Nome *</label>
              <input required value={name} onChange={(e) => setName(e.target.value)} className={inputCls} placeholder="Ex: PostgreSQL Produção" />
            </div>
            <div>
              <label className={labelCls}>Tipo *</label>
              <select required value={dbType} onChange={(e) => handleTypeChange(e.target.value as DbType)} className={inputCls + " bg-white"}>
                {DB_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>Porta *</label>
              <input required type="number" value={port} onChange={(e) => setPort(Number(e.target.value))} className={inputCls} />
            </div>
            <div className="col-span-2">
              <label className={labelCls}>Host / IP *</label>
              <input required value={host} onChange={(e) => setHost(e.target.value)} className={inputCls} placeholder="192.168.1.10 ou db.empresa.com" />
            </div>
            <div className="col-span-2">
              <label className={labelCls}>Nome do banco *</label>
              <input required value={dbName} onChange={(e) => setDbName(e.target.value)} className={inputCls} placeholder="postgres / master / ORCL" />
            </div>
            <div className="col-span-2 border-t pt-3">
              <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">Credenciais</p>
            </div>
            <div>
              <label className={labelCls}>Usuário *</label>
              <input required value={username} onChange={(e) => setUsername(e.target.value)} className={inputCls} autoComplete="off" />
            </div>
            <div>
              <label className={labelCls}>Senha *</label>
              <input required type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} autoComplete="new-password" />
            </div>
            <div className="col-span-2">
              <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-700">
                <input type="checkbox" checked={ssl} onChange={(e) => setSsl(e.target.checked)} className="rounded" />
                Usar SSL/TLS
              </label>
            </div>
            <div className="col-span-2">
              <label className={labelCls}>Descrição (opcional)</label>
              <input value={desc} onChange={(e) => setDesc(e.target.value)} className={inputCls} placeholder="Banco de produção — sistema ERP" />
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 px-6 py-4 border-t">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">Cancelar</button>
          <button type="submit" disabled={mut.isPending} className="flex items-center gap-2 px-4 py-2 text-sm bg-brand-600 hover:bg-brand-700 text-white rounded-lg disabled:opacity-50">
            {mut.isPending && <Loader2 size={14} className="animate-spin" />}
            {initial ? "Salvar" : "Criar"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ── Audit detail ──────────────────────────────────────────────────────────────

function FindingRow({ f }: { f: DbFinding }) {
  const SeverityIcon = f.severity === "high" ? AlertCircle : f.severity === "medium" ? AlertTriangle : Info;
  return (
    <div className="flex items-start gap-3 py-2.5 border-b last:border-0">
      <SeverityIcon size={15} className={`mt-0.5 shrink-0 ${f.severity === "high" ? "text-red-500" : f.severity === "medium" ? "text-yellow-500" : "text-gray-400"}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${SEVERITY_STYLE[f.severity]}`}>
            {FINDING_LABELS[f.type] ?? f.type}
          </span>
          <span className="text-xs text-gray-500 font-mono truncate">{f.user}</span>
        </div>
        <p className="text-xs text-gray-600 mt-0.5">{f.detail}</p>
      </div>
    </div>
  );
}

function AuditDetail({ report }: { report: AuditReport }) {
  const high   = report.findings.filter((f) => f.severity === "high").length;
  const medium = report.findings.filter((f) => f.severity === "medium").length;
  const low    = report.findings.filter((f) => f.severity === "low").length;
  const [tab, setTab] = useState<"findings" | "users">("findings");

  return (
    <div className="space-y-4">
      {/* Metrics */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Usuários", value: report.user_count, color: "text-gray-800" },
          { label: "Críticas", value: high,   color: "text-red-600" },
          { label: "Médias",   value: medium, color: "text-yellow-600" },
          { label: "Baixas",   value: low,    color: "text-gray-500" },
        ].map((m) => (
          <div key={m.label} className="bg-white border rounded-lg p-3 text-center">
            <div className={`text-xl font-bold ${m.color}`}>{m.value}</div>
            <div className="text-xs text-gray-500 mt-0.5">{m.label}</div>
          </div>
        ))}
      </div>

      {/* AI Summary */}
      {report.ai_summary && (
        <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 space-y-2">
          <p className="text-xs font-semibold text-blue-700 uppercase tracking-wide">Análise IA</p>
          <p className="text-sm text-blue-900">{report.ai_summary}</p>
          {report.ai_recommendations.length > 0 && (
            <ul className="mt-2 space-y-1">
              {report.ai_recommendations.map((r, i) => (
                <li key={i} className="flex gap-2 text-xs text-blue-800">
                  <span className="font-bold shrink-0">{i + 1}.</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white border rounded-xl overflow-hidden">
        <div className="flex border-b">
          {[
            { key: "findings", label: `Inconformidades (${report.finding_count})` },
            { key: "users",    label: `Usuários (${report.user_count})` },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key as any)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === key ? "border-brand-600 text-brand-700" : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "findings" && (
          <div className="px-4 py-2 max-h-72 overflow-y-auto">
            {report.findings.length === 0 ? (
              <div className="flex items-center gap-2 py-8 justify-center text-green-600">
                <CheckCircle2 size={18} /> <span className="text-sm">Nenhuma inconformidade detectada</span>
              </div>
            ) : (
              report.findings.map((f, i) => <FindingRow key={i} f={f} />)
            )}
          </div>
        )}

        {tab === "users" && (
          <div className="overflow-x-auto max-h-72 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  {["Usuário", "Superuser", "Pode logar", "Senha expira", "Último acesso", "Dias inativo"].map((h) => (
                    <th key={h} className="text-left px-3 py-2 font-medium text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {report.users.map((u, i) => (
                  <tr key={i} className={`hover:bg-gray-50 ${u.is_system ? "opacity-50" : ""}`}>
                    <td className="px-3 py-2 font-mono font-medium text-gray-800">{u.name}</td>
                    <td className="px-3 py-2">
                      {u.is_superuser ? <span className="text-red-600 font-bold">Sim</span> : <span className="text-gray-400">Não</span>}
                    </td>
                    <td className="px-3 py-2">{u.can_login ? "Sim" : <span className="text-gray-400">Não</span>}</td>
                    <td className="px-3 py-2">
                      {u.password_never_expires ? <span className="text-yellow-600">Nunca</span> : "Sim"}
                    </td>
                    <td className="px-3 py-2 text-gray-500">{u.last_login ? fmtDate(u.last_login) : "—"}</td>
                    <td className="px-3 py-2">
                      {u.days_since_login !== null && u.days_since_login !== undefined ? (
                        <span className={u.days_since_login > 90 ? "text-red-600 font-medium" : "text-gray-600"}>
                          {u.days_since_login}d
                        </span>
                      ) : "—"}
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

// ── Main page ─────────────────────────────────────────────────────────────────

export function DatabaseConnectors() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<DatabaseConnector | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editTarget, setEditTarget] = useState<DatabaseConnector | undefined>();
  const [selectedAudit, setSelectedAudit] = useState<AuditReport | null>(null);

  const { data: connectors = [], isLoading } = useQuery({
    queryKey: ["db-connectors"],
    queryFn: databaseApi.list,
  });

  const { data: audits = [] } = useQuery({
    queryKey: ["db-audits", selected?.id],
    queryFn: () => databaseApi.listAudits(selected!.id),
    enabled: !!selected,
  });

  const testMut = useMutation({
    mutationFn: (id: string) => databaseApi.test(id),
    onSuccess: (res, id) => {
      toast[res.success ? "success" : "error"](res.message);
      qc.invalidateQueries({ queryKey: ["db-connectors"] });
    },
  });

  const auditMut = useMutation({
    mutationFn: (id: string) => databaseApi.runAudit(id),
    onSuccess: (report) => {
      toast.success("Auditoria concluída");
      qc.invalidateQueries({ queryKey: ["db-audits", report.connector_id] });
      setSelectedAudit(report);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Falha na auditoria"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => databaseApi.remove(id),
    onSuccess: () => {
      toast.success("Conector removido");
      setSelected(null);
      qc.invalidateQueries({ queryKey: ["db-connectors"] });
    },
  });

  async function loadAudit(summary: AuditSummary) {
    const full = await databaseApi.getAudit(summary.connector_id, summary.id);
    setSelectedAudit(full);
  }

  return (
    <PageWrapper
      title="Bancos de Dados"
      subtitle="Conecte, teste e audite bancos de dados para detecção de contas e privilégios"
    >
      <div className="flex gap-6 h-[calc(100vh-160px)]">

        {/* Left — connector list */}
        <div className="w-72 shrink-0 flex flex-col gap-3">
          <button
            onClick={() => { setEditTarget(undefined); setShowModal(true); }}
            className="flex items-center gap-2 w-full px-4 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-lg"
          >
            <Plus size={16} /> Novo Conector
          </button>

          <div className="flex-1 overflow-y-auto space-y-1.5">
            {isLoading && (
              <div className="flex justify-center py-8 text-gray-400">
                <Loader2 size={20} className="animate-spin" />
              </div>
            )}
            {!isLoading && connectors.length === 0 && (
              <div className="text-center py-10 text-gray-400 text-sm">
                <Database size={28} className="mx-auto mb-2 opacity-40" />
                Nenhum banco configurado
              </div>
            )}
            {connectors.map((c) => (
              <button
                key={c.id}
                onClick={() => { setSelected(c); setSelectedAudit(null); }}
                className={`w-full text-left px-3 py-3 rounded-lg border transition-colors ${
                  selected?.id === c.id
                    ? "bg-brand-50 border-brand-200"
                    : "bg-white border-gray-200 hover:bg-gray-50"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${DB_COLORS[c.db_type] ?? "bg-gray-100 text-gray-700"}`}>
                    {dbLabel(c.db_type)}
                  </span>
                  {c.last_test_ok === true  && <Wifi size={12} className="text-green-500 ml-auto" />}
                  {c.last_test_ok === false && <WifiOff size={12} className="text-red-500 ml-auto" />}
                </div>
                <p className="text-sm font-medium text-gray-800 mt-1 truncate">{c.name}</p>
                <p className="text-xs text-gray-500 truncate">{c.host}:{c.port}/{c.database_name}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Right — detail panel */}
        <div className="flex-1 overflow-y-auto">
          {!selected ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-3">
              <Database size={40} className="opacity-30" />
              <p className="text-sm">Selecione um conector para ver detalhes</p>
            </div>
          ) : (
            <div className="space-y-5">
              {/* Header */}
              <div className="bg-white border rounded-xl p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${DB_COLORS[selected.db_type] ?? "bg-gray-100"}`}>
                        {dbLabel(selected.db_type)}
                      </span>
                      {selected.last_test_ok === true  && <span className="flex items-center gap-1 text-xs text-green-600"><Wifi size={12} /> Online</span>}
                      {selected.last_test_ok === false && <span className="flex items-center gap-1 text-xs text-red-600"><WifiOff size={12} /> Falhou</span>}
                    </div>
                    <h2 className="text-lg font-semibold text-gray-800">{selected.name}</h2>
                    <p className="text-sm text-gray-500">{selected.host}:{selected.port} / {selected.database_name}</p>
                    {selected.description && <p className="text-xs text-gray-400 mt-1">{selected.description}</p>}
                    {selected.last_test_error && (
                      <p className="text-xs text-red-500 mt-1 flex items-center gap-1">
                        <XCircle size={11} /> {selected.last_test_error}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => testMut.mutate(selected.id)}
                      disabled={testMut.isPending}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 text-gray-600"
                    >
                      {testMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Wifi size={14} />}
                      Testar
                    </button>
                    <button
                      onClick={() => { if (confirm("Executar auditoria? Pode levar alguns segundos.")) auditMut.mutate(selected.id); }}
                      disabled={auditMut.isPending}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-brand-600 hover:bg-brand-700 text-white rounded-lg disabled:opacity-50"
                    >
                      {auditMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                      {auditMut.isPending ? "Auditando..." : "Auditar"}
                    </button>
                    <button
                      onClick={() => { setEditTarget(selected); setShowModal(true); }}
                      className="p-1.5 text-gray-400 hover:text-gray-600 border rounded-lg"
                      title="Editar"
                    >
                      <RefreshCw size={14} />
                    </button>
                    <button
                      onClick={() => { if (confirm(`Remover "${selected.name}"?`)) deleteMut.mutate(selected.id); }}
                      className="p-1.5 text-gray-300 hover:text-red-500 border rounded-lg"
                      title="Remover"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </div>

              {/* Audit history + selected audit */}
              <div className="grid grid-cols-3 gap-5">
                {/* Audit list */}
                <div className="bg-white border rounded-xl overflow-hidden">
                  <div className="px-4 py-3 border-b flex items-center gap-2">
                    <ShieldAlert size={14} className="text-gray-500" />
                    <span className="text-sm font-semibold text-gray-700">Auditorias</span>
                    <span className="text-xs text-gray-400">({audits.length})</span>
                  </div>
                  <div className="divide-y max-h-80 overflow-y-auto">
                    {audits.length === 0 && (
                      <p className="text-sm text-gray-400 text-center py-8">Nenhuma auditoria ainda</p>
                    )}
                    {audits.map((a) => (
                      <button
                        key={a.id}
                        onClick={() => loadAudit(a)}
                        className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                          selectedAudit?.id === a.id ? "bg-brand-50" : ""
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                            a.status === "completed" ? "bg-green-100 text-green-700"
                            : a.status === "failed"  ? "bg-red-100 text-red-700"
                            : "bg-blue-100 text-blue-700"
                          }`}>
                            {a.status === "completed" ? "Concluída" : a.status === "failed" ? "Falhou" : "Rodando"}
                          </span>
                          <ChevronRight size={13} className="text-gray-400" />
                        </div>
                        <p className="text-xs text-gray-500 mt-1">{fmtDate(a.created_at)}</p>
                        {a.status === "completed" && (
                          <p className="text-xs text-gray-600 mt-0.5">
                            {a.user_count} usuários · {a.finding_count > 0
                              ? <span className="text-red-600">{a.finding_count} inconformidades</span>
                              : <span className="text-green-600">OK</span>
                            }
                          </p>
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Audit detail */}
                <div className="col-span-2">
                  {!selectedAudit && !auditMut.isPending && (
                    <div className="flex flex-col items-center justify-center h-64 text-gray-400 gap-2 bg-white border rounded-xl">
                      <ShieldAlert size={32} className="opacity-30" />
                      <p className="text-sm">Selecione uma auditoria ou execute uma nova</p>
                    </div>
                  )}
                  {auditMut.isPending && (
                    <div className="flex flex-col items-center justify-center h-64 gap-3 bg-white border rounded-xl text-brand-600">
                      <Loader2 size={28} className="animate-spin" />
                      <p className="text-sm font-medium">Coletando dados e analisando...</p>
                    </div>
                  )}
                  {selectedAudit && !auditMut.isPending && (
                    <div className="bg-gray-50 rounded-xl p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <p className="text-xs text-gray-500">{fmtDate(selectedAudit.created_at)}</p>
                          {selectedAudit.db_version && (
                            <p className="text-xs text-gray-400 font-mono truncate max-w-xs">{selectedAudit.db_version}</p>
                          )}
                        </div>
                        {selectedAudit.status === "failed" && selectedAudit.error && (
                          <p className="text-xs text-red-600 flex items-center gap-1">
                            <XCircle size={12} /> {selectedAudit.error}
                          </p>
                        )}
                      </div>
                      {selectedAudit.status === "completed" && <AuditDetail report={selectedAudit} />}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {showModal && (
        <ConnectorModal
          initial={editTarget}
          onClose={() => setShowModal(false)}
          onSaved={() => { setShowModal(false); qc.invalidateQueries({ queryKey: ["db-connectors"] }); }}
        />
      )}
    </PageWrapper>
  );
}
