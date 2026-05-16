import { useState, useEffect, useRef } from "react";
import {
  Shield, Clock, Users, Globe, AlertTriangle, CheckCircle2,
  Upload, Settings, BarChart2, List, Loader2, RefreshCw,
  ChevronDown,
} from "lucide-react";
import toast from "react-hot-toast";
import {
  webAuditApi,
  type WebAuditConfig,
  type WebAuditEntry,
  type WebAuditFinding,
  type UserRiskSummary,
  type DomainStats,
} from "../api/webAudit";

type Tab = "dashboard" | "history" | "findings" | "config";

// ── Badges ─────────────────────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  productivity: "bg-green-100 text-green-700",
  social:       "bg-blue-100 text-blue-700",
  streaming:    "bg-purple-100 text-purple-700",
  shadow_it:    "bg-orange-100 text-orange-700",
  malicious:    "bg-red-100 text-red-700",
  suspicious:   "bg-yellow-100 text-yellow-700",
  unknown:      "bg-gray-100 text-gray-600",
};

const CATEGORY_LABELS: Record<string, string> = {
  productivity: "Produtividade",
  social:       "Social",
  streaming:    "Streaming",
  shadow_it:    "Shadow IT",
  malicious:    "Malicioso",
  suspicious:   "Suspeito",
  unknown:      "Desconhecido",
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  high:     "bg-orange-100 text-orange-700",
  medium:   "bg-yellow-100 text-yellow-700",
  low:      "bg-gray-100 text-gray-600",
};

const SEVERITY_LABELS: Record<string, string> = {
  critical: "Crítico",
  high:     "Alto",
  medium:   "Médio",
  low:      "Baixo",
};

const RISK_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  high:     "bg-orange-100 text-orange-700",
  medium:   "bg-yellow-100 text-yellow-700",
  low:      "bg-green-100 text-green-700",
};

function CategoryBadge({ category }: { category: string }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${CATEGORY_COLORS[category] ?? CATEGORY_COLORS.unknown}`}>
      {CATEGORY_LABELS[category] ?? category}
    </span>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${SEVERITY_COLORS[severity] ?? SEVERITY_COLORS.low}`}>
      {SEVERITY_LABELS[severity] ?? severity}
    </span>
  );
}

function RiskBadge({ level }: { level: string }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${RISK_COLORS[level] ?? RISK_COLORS.low}`}>
      {SEVERITY_LABELS[level] ?? level}
    </span>
  );
}

// ── Dashboard Tab ──────────────────────────────────────────────────────────────

function DashboardTab() {
  const [entries, setEntries] = useState<WebAuditEntry[]>([]);
  const [findings, setFindings] = useState<WebAuditFinding[]>([]);
  const [userStats, setUserStats] = useState<UserRiskSummary[]>([]);
  const [domainStats, setDomainStats] = useState<DomainStats[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      webAuditApi.getEntries({ days: 30, limit: 200 }),
      webAuditApi.getFindings({ limit: 200 }),
      webAuditApi.getUserStats(30),
      webAuditApi.getDomainStats(30, 10),
    ])
      .then(([e, f, u, d]) => {
        setEntries(e);
        setFindings(f);
        setUserStats(u);
        setDomainStats(d);
      })
      .catch(() => toast.error("Erro ao carregar dashboard"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    );
  }

  const criticalFindings = findings.filter(f => f.severity === "critical").length;
  const highRiskUsers = userStats.filter(u => u.risk_level === "critical" || u.risk_level === "high").length;

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-3">
            <Globe className="w-8 h-8 text-blue-500" />
            <div>
              <p className="text-2xl font-bold text-gray-900">{entries.length}</p>
              <p className="text-sm text-gray-500">Entradas (30 dias)</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-8 h-8 text-red-500" />
            <div>
              <p className="text-2xl font-bold text-gray-900">{criticalFindings}</p>
              <p className="text-sm text-gray-500">Findings críticos</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-3">
            <Users className="w-8 h-8 text-orange-500" />
            <div>
              <p className="text-2xl font-bold text-gray-900">{highRiskUsers}</p>
              <p className="text-sm text-gray-500">Usuários de risco</p>
            </div>
          </div>
        </div>
      </div>

      {/* Top users table */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="font-semibold text-gray-900">Top usuários por risco</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
              <tr>
                <th className="px-4 py-3 text-left">Usuário</th>
                <th className="px-4 py-3 text-left">Departamento</th>
                <th className="px-4 py-3 text-right">Visitas</th>
                <th className="px-4 py-3 text-right">Maliciosos</th>
                <th className="px-4 py-3 text-right">Shadow IT</th>
                <th className="px-4 py-3 text-right">Produtividade</th>
                <th className="px-4 py-3 text-left">Risco</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {userStats.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-400">Nenhum dado disponível</td>
                </tr>
              ) : userStats.map((u, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{u.ad_user}</td>
                  <td className="px-4 py-3 text-gray-500">{u.department ?? "—"}</td>
                  <td className="px-4 py-3 text-right text-gray-700">{u.total_visits}</td>
                  <td className="px-4 py-3 text-right">
                    <span className={u.malicious_count > 0 ? "text-red-600 font-semibold" : "text-gray-500"}>
                      {u.malicious_count}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={u.shadow_it_count > 0 ? "text-orange-600 font-semibold" : "text-gray-500"}>
                      {u.shadow_it_count}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 bg-gray-200 rounded-full h-1.5">
                        <div
                          className="bg-green-500 h-1.5 rounded-full"
                          style={{ width: `${u.productivity_score}%` }}
                        />
                      </div>
                      <span className="text-gray-700 w-8">{u.productivity_score}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-3"><RiskBadge level={u.risk_level} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Top domains table */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="font-semibold text-gray-900">Top domínios acessados</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
              <tr>
                <th className="px-4 py-3 text-left">Domínio</th>
                <th className="px-4 py-3 text-left">Categoria</th>
                <th className="px-4 py-3 text-right">Visitas</th>
                <th className="px-4 py-3 text-right">Usuários únicos</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {domainStats.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-gray-400">Nenhum dado disponível</td>
                </tr>
              ) : domainStats.map((d, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-gray-800">{d.domain}</td>
                  <td className="px-4 py-3"><CategoryBadge category={d.category} /></td>
                  <td className="px-4 py-3 text-right text-gray-700">{d.visit_count}</td>
                  <td className="px-4 py-3 text-right text-gray-700">{d.unique_users}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ── History Tab ────────────────────────────────────────────────────────────────

function HistoryTab() {
  const [entries, setEntries] = useState<WebAuditEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [workstation, setWorkstation] = useState("");
  const [adUser, setAdUser] = useState("");
  const [category, setCategory] = useState("");
  const [days, setDays] = useState(30);

  function load() {
    setLoading(true);
    webAuditApi.getEntries({
      workstation: workstation || undefined,
      ad_user: adUser || undefined,
      category: category || undefined,
      days,
      limit: 200,
    })
      .then(setEntries)
      .catch(() => toast.error("Erro ao carregar histórico"))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Usuário AD</label>
            <input
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-44 focus:outline-none focus:ring-2 focus:ring-brand-400"
              placeholder="ex: joao.silva"
              value={adUser}
              onChange={e => setAdUser(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Categoria</label>
            <select
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-44 focus:outline-none focus:ring-2 focus:ring-brand-400"
              value={category}
              onChange={e => setCategory(e.target.value)}
            >
              <option value="">Todas</option>
              {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Período</label>
            <select
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
              value={days}
              onChange={e => setDays(Number(e.target.value))}
            >
              <option value={7}>7 dias</option>
              <option value={30}>30 dias</option>
              <option value={90}>90 dias</option>
            </select>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700"
          >
            <RefreshCw className="w-4 h-4" />
            Filtrar
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="overflow-x-auto">
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="w-6 h-6 text-brand-500 animate-spin" />
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
                <tr>
                  <th className="px-4 py-3 text-left">Estação</th>
                  <th className="px-4 py-3 text-left">Usuário</th>
                  <th className="px-4 py-3 text-left">Domínio</th>
                  <th className="px-4 py-3 text-left">Categoria</th>
                  <th className="px-4 py-3 text-right">Visitas</th>
                  <th className="px-4 py-3 text-left">Data</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {entries.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-400">Nenhuma entrada encontrada</td>
                  </tr>
                ) : entries.map(e => (
                  <tr key={e.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-700 font-mono text-xs">{e.workstation}</td>
                    <td className="px-4 py-3 text-gray-700">{e.ad_user ?? "—"}</td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-800 max-w-[200px] truncate" title={e.domain}>{e.domain}</td>
                    <td className="px-4 py-3"><CategoryBadge category={e.category} /></td>
                    <td className="px-4 py-3 text-right text-gray-700">{e.visit_count}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                      {new Date(e.visited_at).toLocaleString("pt-BR")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Findings Tab ───────────────────────────────────────────────────────────────

function FindingsTab() {
  const [findings, setFindings] = useState<WebAuditFinding[]>([]);
  const [loading, setLoading] = useState(false);
  const [severity, setSeverity] = useState("");
  const [findingType, setFindingType] = useState("");

  function load() {
    setLoading(true);
    webAuditApi.getFindings({
      severity: severity || undefined,
      finding_type: findingType || undefined,
      limit: 200,
    })
      .then(setFindings)
      .catch(() => toast.error("Erro ao carregar findings"))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Severidade</label>
            <select
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
              value={severity}
              onChange={e => setSeverity(e.target.value)}
            >
              <option value="">Todas</option>
              {Object.entries(SEVERITY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Tipo</label>
            <select
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
              value={findingType}
              onChange={e => setFindingType(e.target.value)}
            >
              <option value="">Todos</option>
              <option value="malicious_site">Site malicioso</option>
              <option value="shadow_it">Shadow IT</option>
              <option value="policy_violation">Violação de política</option>
            </select>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700"
          >
            <RefreshCw className="w-4 h-4" />
            Filtrar
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="overflow-x-auto">
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="w-6 h-6 text-brand-500 animate-spin" />
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
                <tr>
                  <th className="px-4 py-3 text-left">Severidade</th>
                  <th className="px-4 py-3 text-left">Domínio</th>
                  <th className="px-4 py-3 text-left">Tipo</th>
                  <th className="px-4 py-3 text-left">Usuário</th>
                  <th className="px-4 py-3 text-left">Descrição</th>
                  <th className="px-4 py-3 text-left">Recomendação</th>
                  <th className="px-4 py-3 text-left">Data</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {findings.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-gray-400">Nenhum finding encontrado</td>
                  </tr>
                ) : findings.map(f => (
                  <tr key={f.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3"><SeverityBadge severity={f.severity} /></td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-800 max-w-[160px] truncate" title={f.domain}>{f.domain}</td>
                    <td className="px-4 py-3 text-gray-600">{f.finding_type}</td>
                    <td className="px-4 py-3 text-gray-700">{f.ad_user ?? "—"}</td>
                    <td className="px-4 py-3 text-gray-600 max-w-[200px] truncate" title={f.description}>{f.description}</td>
                    <td className="px-4 py-3 text-gray-500 max-w-[180px] truncate" title={f.recommendation ?? ""}>{f.recommendation ?? "—"}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                      {new Date(f.created_at).toLocaleString("pt-BR")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Config Tab ─────────────────────────────────────────────────────────────────

function ConfigTab() {
  const [cfg, setCfg] = useState<WebAuditConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  // Upload form state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadWorkstation, setUploadWorkstation] = useState("");
  const [uploadAdUser, setUploadAdUser] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    webAuditApi.getConfig()
      .then(setCfg)
      .catch(() => toast.error("Erro ao carregar configuração"));
  }, []);

  async function handleSave() {
    if (!cfg) return;
    setSaving(true);
    try {
      const updated = await webAuditApi.updateConfig({
        enabled: cfg.enabled,
        collection_method: cfg.collection_method,
        gpo_share_path: cfg.gpo_share_path,
        poll_interval_minutes: cfg.poll_interval_minutes,
        retention_days: cfg.retention_days,
        alert_on_malicious: cfg.alert_on_malicious,
        alert_on_shadow_it: cfg.alert_on_shadow_it,
      });
      setCfg(updated);
      toast.success("Configuração salva");
    } catch {
      toast.error("Erro ao salvar configuração");
    } finally {
      setSaving(false);
    }
  }

  async function handleUpload() {
    if (!uploadFile || !uploadWorkstation.trim()) {
      toast.error("Arquivo e nome da estação são obrigatórios");
      return;
    }
    setUploading(true);
    try {
      const result = await webAuditApi.uploadHistory(
        uploadFile, uploadWorkstation, uploadAdUser || undefined
      );
      toast.success(`${result.ingested} entradas importadas com sucesso`);
      setUploadFile(null);
      setUploadWorkstation("");
      setUploadAdUser("");
      if (fileRef.current) fileRef.current.value = "";
    } catch {
      toast.error("Erro ao importar histórico");
    } finally {
      setUploading(false);
    }
  }

  async function handleAnalyze() {
    setAnalyzing(true);
    try {
      const result = await webAuditApi.triggerAnalysis();
      toast.success(`${result.analyzed} entradas analisadas pela IA`);
    } catch {
      toast.error("Erro ao acionar análise IA");
    } finally {
      setAnalyzing(false);
    }
  }

  if (!cfg) {
    return (
      <div className="flex items-center justify-center h-40">
        <Loader2 className="w-6 h-6 text-brand-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Config form */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="font-semibold text-gray-900 mb-4">Configurações gerais</h3>
        <div className="space-y-4">
          {/* Enabled toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-900">Auditoria habilitada</p>
              <p className="text-sm text-gray-500">Ativar coleta e análise de histórico de navegação</p>
            </div>
            <button
              onClick={() => setCfg({ ...cfg, enabled: !cfg.enabled })}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${cfg.enabled ? "bg-brand-600" : "bg-gray-300"}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${cfg.enabled ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          </div>

          {/* Collection method */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Método de coleta</label>
            <select
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-full max-w-xs focus:outline-none focus:ring-2 focus:ring-brand-400"
              value={cfg.collection_method}
              onChange={e => setCfg({ ...cfg, collection_method: e.target.value })}
            >
              <option value="agent">Agente</option>
              <option value="gpo">GPO Logoff Script</option>
              <option value="manual">Upload manual</option>
            </select>
          </div>

          {/* GPO share path */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Caminho do share GPO</label>
            <input
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-full max-w-md focus:outline-none focus:ring-2 focus:ring-brand-400"
              placeholder="\\\\servidor\\audit"
              value={cfg.gpo_share_path ?? ""}
              onChange={e => setCfg({ ...cfg, gpo_share_path: e.target.value || null })}
            />
          </div>

          {/* Poll interval */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Intervalo de coleta (minutos)</label>
            <input
              type="number"
              min={10}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-32 focus:outline-none focus:ring-2 focus:ring-brand-400"
              value={cfg.poll_interval_minutes}
              onChange={e => setCfg({ ...cfg, poll_interval_minutes: Number(e.target.value) })}
            />
          </div>

          {/* Retention */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Retenção de dados (dias)</label>
            <input
              type="number"
              min={7}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-32 focus:outline-none focus:ring-2 focus:ring-brand-400"
              value={cfg.retention_days}
              onChange={e => setCfg({ ...cfg, retention_days: Number(e.target.value) })}
            />
          </div>

          {/* Alert toggles */}
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-900">Alertar em sites maliciosos</p>
              <p className="text-sm text-gray-500">Gera finding crítico para domínios maliciosos</p>
            </div>
            <button
              onClick={() => setCfg({ ...cfg, alert_on_malicious: !cfg.alert_on_malicious })}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${cfg.alert_on_malicious ? "bg-brand-600" : "bg-gray-300"}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${cfg.alert_on_malicious ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-900">Alertar em Shadow IT</p>
              <p className="text-sm text-gray-500">Gera finding para uso de cloud não aprovado</p>
            </div>
            <button
              onClick={() => setCfg({ ...cfg, alert_on_shadow_it: !cfg.alert_on_shadow_it })}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${cfg.alert_on_shadow_it ? "bg-brand-600" : "bg-gray-300"}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${cfg.alert_on_shadow_it ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          </div>
        </div>

        <div className="mt-6">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
            Salvar configurações
          </button>
        </div>
      </div>

      {/* Upload CSV */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="font-semibold text-gray-900 mb-1">Upload de histórico CSV</h3>
        <p className="text-sm text-gray-500 mb-4">Importe o CSV gerado pelo BrowsingHistoryView para uma estação específica.</p>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Arquivo CSV</label>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.tsv,.txt"
              className="block text-sm text-gray-700"
              onChange={e => setUploadFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div className="flex gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Nome da estação *</label>
              <input
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-brand-400"
                placeholder="ex: PC-JOAO-01"
                value={uploadWorkstation}
                onChange={e => setUploadWorkstation(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Usuário AD</label>
              <input
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-brand-400"
                placeholder="ex: joao.silva"
                value={uploadAdUser}
                onChange={e => setUploadAdUser(e.target.value)}
              />
            </div>
          </div>
          <button
            onClick={handleUpload}
            disabled={uploading || !uploadFile}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            Importar histórico
          </button>
        </div>
      </div>

      {/* AI Analysis */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="font-semibold text-gray-900 mb-1">Análise com IA</h3>
        <p className="text-sm text-gray-500 mb-4">
          Classifica entradas ainda não analisadas usando Claude Haiku. Processa até 100 entradas por execução.
        </p>
        <button
          onClick={handleAnalyze}
          disabled={analyzing}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 disabled:opacity-50"
        >
          {analyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
          Analisar com IA
        </button>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────

const TABS: { key: Tab; label: string; icon: React.FC<{ className?: string }> }[] = [
  { key: "dashboard", label: "Dashboard", icon: BarChart2 },
  { key: "history",   label: "Histórico",  icon: Clock },
  { key: "findings",  label: "Findings",   icon: AlertTriangle },
  { key: "config",    label: "Configuração", icon: Settings },
];

export default function WebAuditPage() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Globe className="w-7 h-7 text-brand-600" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Web Audit</h1>
          <p className="text-sm text-gray-500">Auditoria de navegação web por estação e usuário AD</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map(t => {
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors ${
                tab === t.key
                  ? "text-brand-600 border-b-2 border-brand-600 bg-brand-50"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {tab === "dashboard" && <DashboardTab />}
      {tab === "history"   && <HistoryTab />}
      {tab === "findings"  && <FindingsTab />}
      {tab === "config"    && <ConfigTab />}
    </div>
  );
}
