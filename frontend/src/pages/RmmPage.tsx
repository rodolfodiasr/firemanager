import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Server, RefreshCw, CheckCircle, AlertCircle,
  ChevronRight, Loader2, FlaskConical, Terminal,
  Code2, Clock, X, Play, Wifi, WifiOff, AlertTriangle,
  Monitor, History, Settings, BookOpen, Plus, Pencil,
  Trash2, Lock, Save,
} from "lucide-react";
import toast from "react-hot-toast";
import {
  rmmApi, rmmTemplatesApi,
  type RmmIntegration, type RmmAgent, type RmmScriptRun, type RmmScriptTemplate,
  type TemplateCategory, type TemplateShell,
} from "../api/rmm";

const RMM_TYPE_LABELS: Record<string, string> = {
  tactical_rmm: "Tactical RMM",
  ninja_rmm: "NinjaRMM",
  atera: "Atera",
  connectwise_automate: "ConnectWise Automate",
};

const SHELLS = [
  { value: "powershell", label: "PowerShell" },
  { value: "cmd", label: "CMD" },
  { value: "bash", label: "Bash" },
  { value: "python", label: "Python" },
];

const CATEGORIES = [
  { value: "monitoring", label: "Monitoramento" },
  { value: "security", label: "Segurança" },
  { value: "maintenance", label: "Manutenção" },
  { value: "network", label: "Rede" },
  { value: "general", label: "Geral" },
  { value: "incident_response", label: "Resp. Incidente" },
  { value: "identity", label: "Identidade" },
  { value: "compliance", label: "Compliance" },
  { value: "forensics", label: "Forense" },
];

const CATEGORY_LABELS: Record<string, string> = Object.fromEntries(CATEGORIES.map((c) => [c.value, c.label]));

const CATEGORY_COLORS: Record<string, string> = {
  monitoring: "bg-blue-100 text-blue-700",
  security: "bg-red-100 text-red-700",
  maintenance: "bg-amber-100 text-amber-700",
  network: "bg-green-100 text-green-700",
  general: "bg-gray-100 text-gray-600",
  incident_response: "bg-rose-100 text-rose-700",
  identity: "bg-purple-100 text-purple-700",
  compliance: "bg-sky-100 text-sky-700",
  forensics: "bg-orange-100 text-orange-700",
};

// ── Small helpers ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string | null }) {
  if (status === "ok") return <span className="flex items-center gap-1 text-xs text-green-600"><CheckCircle size={11} />OK</span>;
  if (status === "error") return <span className="flex items-center gap-1 text-xs text-red-500"><AlertCircle size={11} />Erro</span>;
  return <span className="text-xs text-gray-400">—</span>;
}

function AgentDot({ status }: { status: string }) {
  return status === "online"
    ? <span className="w-2 h-2 rounded-full bg-green-500 inline-block shrink-0" />
    : <span className="w-2 h-2 rounded-full bg-gray-300 inline-block shrink-0" />;
}

function RunStatusBadge({ status }: { status: string }) {
  const cls: Record<string, string> = {
    success: "bg-green-100 text-green-700",
    error: "bg-red-100 text-red-600",
    running: "bg-blue-100 text-blue-700",
    pending: "bg-gray-100 text-gray-600",
  };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${cls[status] ?? cls.pending}`}>
      {status}
    </span>
  );
}

function formatDate(s: string | null) {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

// ── Template Form Modal ───────────────────────────────────────────────────────

interface TemplateFormProps {
  initial?: RmmScriptTemplate | null;
  prefill?: { shell: string; run_type: string; body: string };
  onClose: () => void;
  onSaved: (tmpl: RmmScriptTemplate) => void;
}

function TemplateFormModal({ initial, prefill, onClose, onSaved }: TemplateFormProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [category, setCategory] = useState<string>(initial?.category ?? "general");
  const [shell, setShell] = useState<string>(initial?.shell ?? prefill?.shell ?? "powershell");
  const [runType, setRunType] = useState<"command" | "script">(
    (initial?.run_type ?? prefill?.run_type ?? "command") as "command" | "script"
  );
  const [body, setBody] = useState(initial?.body ?? prefill?.body ?? "");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name.trim()) { toast.error("Nome obrigatório."); return; }
    if (!body.trim()) { toast.error("Corpo obrigatório."); return; }
    setSaving(true);
    try {
      let saved: RmmScriptTemplate;
      if (initial) {
        saved = await rmmTemplatesApi.update(initial.id, { name, description, category: category as TemplateCategory, shell: shell as TemplateShell, run_type: runType, body });
        toast.success("Template atualizado.");
      } else {
        saved = await rmmTemplatesApi.create({ name, description, category, shell, run_type: runType, body });
        toast.success("Template criado.");
      }
      onSaved(saved);
    } catch {
      toast.error("Erro ao salvar template.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl flex flex-col max-h-[92vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h3 className="font-semibold text-gray-800 flex items-center gap-2">
            <BookOpen size={16} />
            {initial ? "Editar Template" : "Novo Template"}
          </h3>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>

        <div className="p-5 flex-1 overflow-auto space-y-4">
          {/* Name */}
          <div>
            <label className="text-xs font-medium text-gray-600">Nome *</label>
            <input
              className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Ex: Listar processos em execução"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          {/* Description */}
          <div>
            <label className="text-xs font-medium text-gray-600">Descrição</label>
            <input
              className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Para que serve este template..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {/* Category + Shell + Run type */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-600">Categoria</label>
              <select
                className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600">Shell</label>
              <select
                className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                value={shell}
                onChange={(e) => setShell(e.target.value)}
              >
                {SHELLS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600">Tipo</label>
              <div className="flex gap-1 mt-1 bg-gray-100 rounded-lg p-1">
                {(["command", "script"] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setRunType(t)}
                    className={`flex-1 flex items-center justify-center gap-1 py-1.5 rounded-md text-xs font-medium transition-all ${runType === t ? "bg-white shadow-sm text-gray-900" : "text-gray-500"}`}
                  >
                    {t === "command" ? <Terminal size={11} /> : <Code2 size={11} />}
                    {t === "command" ? "Cmd" : "Script"}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Body */}
          <div>
            <label className="text-xs font-medium text-gray-600">
              {runType === "command" ? "Comando *" : "Script *"}
            </label>
            <textarea
              className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono resize-none"
              rows={runType === "command" ? 3 : 10}
              placeholder={runType === "command"
                ? "Get-Process | Select-Object -First 10 Name, CPU"
                : "# Script PowerShell\n$info = Get-ComputerInfo\nWrite-Output $info.OsName"}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 px-5 py-4 border-t border-gray-100">
          <button onClick={onClose} className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200">
            Cancelar
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700 disabled:opacity-50"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {saving ? "Salvando..." : "Salvar Template"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Templates Panel ───────────────────────────────────────────────────────────

function TemplatesPanel() {
  const [templates, setTemplates] = useState<RmmScriptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [formModal, setFormModal] = useState<{ open: boolean; editing: RmmScriptTemplate | null }>({ open: false, editing: null });
  const [deleting, setDeleting] = useState<string | null>(null);
  const [viewBody, setViewBody] = useState<RmmScriptTemplate | null>(null);

  useEffect(() => { loadTemplates(); }, []);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const data = await rmmTemplatesApi.list();
      setTemplates(data);
    } catch {
      toast.error("Erro ao carregar templates.");
    } finally {
      setLoading(false);
    }
  };

  const handleSaved = (saved: RmmScriptTemplate) => {
    setTemplates((prev) => {
      const idx = prev.findIndex((t) => t.id === saved.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next;
      }
      return [saved, ...prev];
    });
    setFormModal({ open: false, editing: null });
  };

  const handleDelete = async (tmpl: RmmScriptTemplate) => {
    if (!confirm(`Remover template "${tmpl.name}"?`)) return;
    setDeleting(tmpl.id);
    try {
      await rmmTemplatesApi.delete(tmpl.id);
      setTemplates((prev) => prev.filter((t) => t.id !== tmpl.id));
      toast.success("Template removido.");
    } catch {
      toast.error("Erro ao remover template.");
    } finally {
      setDeleting(null); }
  };

  const categories = ["all", ...Array.from(new Set(templates.map((t) => t.category)))];

  const filtered = templates.filter((t) => {
    const matchCat = categoryFilter === "all" || t.category === categoryFilter;
    const matchQ = !searchQuery || t.name.toLowerCase().includes(searchQuery.toLowerCase()) || (t.description ?? "").toLowerCase().includes(searchQuery.toLowerCase());
    return matchCat && matchQ;
  });

  const builtinCount = filtered.filter((t) => t.is_builtin).length;
  const customCount = filtered.filter((t) => !t.is_builtin).length;

  return (
    <div className="bg-white border border-gray-200 rounded-xl flex flex-col min-h-[500px]">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-5 py-3 border-b border-gray-100 flex-wrap">
        <input
          className="flex-1 min-w-[180px] border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
          placeholder="Buscar templates..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <div className="flex gap-1 bg-gray-100 rounded-lg p-0.5 flex-wrap">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${categoryFilter === cat ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"}`}
            >
              {cat === "all" ? "Todos" : CATEGORY_LABELS[cat] ?? cat}
            </button>
          ))}
        </div>
        <button
          onClick={() => setFormModal({ open: true, editing: null })}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 text-white rounded-lg text-xs font-medium hover:bg-brand-700"
        >
          <Plus size={13} /> Novo Template
        </button>
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-4 px-5 py-2 bg-gray-50 border-b border-gray-100 text-xs text-gray-500">
        <span><strong className="text-gray-700">{builtinCount}</strong> builtin</span>
        <span><strong className="text-gray-700">{customCount}</strong> customizados</span>
        <span className="text-gray-300">|</span>
        <span><strong className="text-gray-700">{filtered.length}</strong> exibidos</span>
      </div>

      {/* List */}
      {loading ? (
        <div className="flex justify-center py-16"><Loader2 size={24} className="animate-spin text-gray-300" /></div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-gray-300">
          <BookOpen size={40} className="mb-3 opacity-30" />
          <p className="text-sm">Nenhum template encontrado.</p>
        </div>
      ) : (
        <div className="divide-y divide-gray-50 overflow-auto flex-1">
          {filtered.map((tmpl) => (
            <div
              key={tmpl.id}
              className="flex items-start gap-4 px-5 py-3.5 hover:bg-gray-50 transition-colors group"
            >
              {/* Icon */}
              <div className="mt-0.5 shrink-0 text-gray-300 group-hover:text-brand-400 transition-colors">
                {tmpl.run_type === "script" ? <Code2 size={16} /> : <Terminal size={16} />}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-medium text-gray-800">{tmpl.name}</p>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${CATEGORY_COLORS[tmpl.category] ?? "bg-gray-100 text-gray-500"}`}>
                    {CATEGORY_LABELS[tmpl.category] ?? tmpl.category}
                  </span>
                  <span className="text-[10px] text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">{tmpl.shell}</span>
                  {tmpl.is_builtin && (
                    <span className="flex items-center gap-0.5 text-[10px] text-gray-400">
                      <Lock size={9} /> builtin
                    </span>
                  )}
                </div>
                {tmpl.description && (
                  <p className="text-xs text-gray-400 mt-0.5 truncate">{tmpl.description}</p>
                )}
                <button
                  onClick={() => setViewBody(viewBody?.id === tmpl.id ? null : tmpl)}
                  className="text-[10px] text-brand-500 hover:underline mt-1"
                >
                  {viewBody?.id === tmpl.id ? "Ocultar código" : "Ver código"}
                </button>
                {viewBody?.id === tmpl.id && (
                  <pre className="mt-2 text-[11px] bg-gray-950 text-green-400 p-3 rounded-lg font-mono whitespace-pre-wrap max-h-40 overflow-auto">
                    {tmpl.body}
                  </pre>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                {!tmpl.is_builtin && (
                  <>
                    <button
                      onClick={() => setFormModal({ open: true, editing: tmpl })}
                      title="Editar"
                      className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-brand-50 rounded-lg transition-colors"
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      onClick={() => handleDelete(tmpl)}
                      disabled={deleting === tmpl.id}
                      title="Remover"
                      className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                    >
                      {deleting === tmpl.id ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Form modal */}
      {formModal.open && (
        <TemplateFormModal
          initial={formModal.editing}
          onClose={() => setFormModal({ open: false, editing: null })}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}

// ── Run Modal ─────────────────────────────────────────────────────────────────

interface RunModalProps {
  integration: RmmIntegration;
  agent: RmmAgent;
  onClose: () => void;
  onSuccess: (run: RmmScriptRun) => void;
}

function RunModal({ integration, agent, onClose, onSuccess }: RunModalProps) {
  const [tab, setTab] = useState<"command" | "script">("command");
  const [shell, setShell] = useState("powershell");
  const [body, setBody] = useState("");
  const [timeout, setTimeout_] = useState(60);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RmmScriptRun | null>(null);
  const [templates, setTemplates] = useState<RmmScriptTemplate[]>([]);
  const [showTemplates, setShowTemplates] = useState(false);
  const [templateFilter, setTemplateFilter] = useState("all");
  const [saveModal, setSaveModal] = useState(false);

  useEffect(() => {
    rmmTemplatesApi.list().then(setTemplates).catch(() => {});
  }, []);

  const applyTemplate = (tmpl: RmmScriptTemplate) => {
    setTab(tmpl.run_type as "command" | "script");
    setShell(tmpl.shell);
    setBody(tmpl.body);
    setResult(null);
    setShowTemplates(false);
    toast.success(`Template "${tmpl.name}" aplicado.`);
  };

  const handleRun = async () => {
    if (!body.trim()) { toast.error("Digite um comando ou script."); return; }
    setLoading(true);
    setResult(null);
    try {
      const run = await rmmApi.run(integration.id, agent.external_id, {
        run_type: tab,
        shell,
        body: body.trim(),
        timeout,
      });
      setResult(run);
      onSuccess(run);
      toast.success(run.status === "success" ? "Executado com sucesso." : "Executado com erros.");
    } catch {
      toast.error("Falha ao enviar comando ao agente.");
    } finally {
      setLoading(false);
    }
  };

  const templateCategories = ["all", ...Array.from(new Set(templates.map((t) => t.category)))];
  const filteredTemplates = templateFilter === "all" ? templates : templates.filter((t) => t.category === templateFilter);

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl flex flex-col max-h-[90vh]">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <div>
              <h3 className="font-semibold text-gray-800 flex items-center gap-2"><Terminal size={16} />Executar no Agente</h3>
              <p className="text-xs text-gray-500 mt-0.5">{agent.hostname} · {agent.ip_address || "IP desconhecido"}</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowTemplates((v) => !v)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${showTemplates ? "bg-brand-50 border-brand-200 text-brand-700" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}
              >
                <BookOpen size={12} /> Templates
              </button>
              <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>
          </div>

          {/* Template panel */}
          {showTemplates && (
            <div className="border-b border-gray-100 bg-gray-50">
              <div className="flex gap-1 px-4 pt-3 pb-2 overflow-x-auto">
                {templateCategories.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setTemplateFilter(cat)}
                    className={`shrink-0 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${templateFilter === cat ? "bg-brand-600 text-white" : "bg-white border border-gray-200 text-gray-600 hover:border-brand-300"}`}
                  >
                    {cat === "all" ? "Todos" : CATEGORY_LABELS[cat] ?? cat}
                  </button>
                ))}
              </div>
              <div className="max-h-48 overflow-auto px-4 pb-3 space-y-1">
                {filteredTemplates.length === 0 && (
                  <p className="text-xs text-gray-400 text-center py-4">Nenhum template.</p>
                )}
                {filteredTemplates.map((tmpl) => (
                  <button
                    key={tmpl.id}
                    onClick={() => applyTemplate(tmpl)}
                    className="w-full text-left flex items-start gap-3 px-3 py-2.5 rounded-lg bg-white border border-gray-100 hover:border-brand-300 hover:bg-brand-50 transition-colors group"
                  >
                    <div className="mt-0.5 shrink-0">
                      {tmpl.run_type === "command" ? <Terminal size={12} className="text-gray-400 group-hover:text-brand-500" /> : <Code2 size={12} className="text-gray-400 group-hover:text-brand-500" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-gray-800 truncate">{tmpl.name}</p>
                      {tmpl.description && <p className="text-[10px] text-gray-400 truncate mt-0.5">{tmpl.description}</p>}
                    </div>
                    <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded ${CATEGORY_COLORS[tmpl.category] ?? "bg-gray-100 text-gray-500"}`}>
                      {CATEGORY_LABELS[tmpl.category] ?? tmpl.category}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="p-5 flex-1 overflow-auto space-y-4">
            {/* Tabs */}
            <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
              {(["command", "script"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => { setTab(t); setBody(""); setResult(null); }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${tab === t ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"}`}
                >
                  {t === "command" ? <Terminal size={12} /> : <Code2 size={12} />}
                  {t === "command" ? "Comando Rápido" : "Script"}
                </button>
              ))}
            </div>

            {/* Shell + Timeout */}
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-xs font-medium text-gray-600">Shell</label>
                <select
                  className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                  value={shell}
                  onChange={(e) => setShell(e.target.value)}
                >
                  {SHELLS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>
              <div className="w-32">
                <label className="text-xs font-medium text-gray-600">Timeout (s)</label>
                <input
                  type="number" min={5} max={300}
                  className="w-full mt-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                  value={timeout}
                  onChange={(e) => setTimeout_(Number(e.target.value))}
                />
              </div>
            </div>

            {/* Body */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-gray-600">
                  {tab === "command" ? "Comando" : "Script"}
                </label>
                {body.trim() && (
                  <button
                    onClick={() => setSaveModal(true)}
                    className="flex items-center gap-1 text-[11px] text-brand-600 hover:underline"
                  >
                    <Save size={10} /> Salvar como template
                  </button>
                )}
              </div>
              <textarea
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono resize-none"
                rows={tab === "command" ? 2 : 8}
                placeholder={tab === "command"
                  ? "Get-Process | Select-Object -First 5"
                  : "# Script PowerShell\nGet-ComputerInfo | Select-Object OsName, TotalPhysicalMemory"}
                value={body}
                onChange={(e) => setBody(e.target.value)}
              />
            </div>

            {/* Result */}
            {result && (
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-100">
                  <span className="text-xs font-medium text-gray-600">Saída</span>
                  <div className="flex items-center gap-2">
                    <RunStatusBadge status={result.status} />
                    {result.exit_code != null && (
                      <span className="text-[10px] text-gray-400">exit: {result.exit_code}</span>
                    )}
                  </div>
                </div>
                <pre className="text-xs p-3 font-mono whitespace-pre-wrap max-h-48 overflow-auto bg-gray-950 text-green-400">
                  {result.output || "(sem saída)"}
                </pre>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 px-5 py-4 border-t border-gray-100">
            <button onClick={onClose} className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200">Fechar</button>
            <button
              onClick={handleRun}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700 disabled:opacity-50"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
              {loading ? "Executando..." : "Executar"}
            </button>
          </div>
        </div>
      </div>

      {/* Save-as-template modal */}
      {saveModal && (
        <TemplateFormModal
          prefill={{ shell, run_type: tab, body }}
          onClose={() => setSaveModal(false)}
          onSaved={() => { setSaveModal(false); toast.success("Template salvo!"); }}
        />
      )}
    </>
  );
}

// ── Agent Detail Panel ────────────────────────────────────────────────────────

interface AgentDetailProps {
  agent: RmmAgent;
  integration: RmmIntegration;
  onRun: (agent: RmmAgent) => void;
  onClose: () => void;
  runs: RmmScriptRun[];
  loadingRuns: boolean;
}

function AgentDetail({ agent, integration, onRun, onClose, runs, loadingRuns }: AgentDetailProps) {
  const [tab, setTab] = useState<"info" | "history">("info");

  return (
    <div className="border border-gray-200 rounded-xl bg-white flex flex-col h-full">
      <div className="flex items-start justify-between p-4 border-b border-gray-100">
        <div className="flex items-center gap-2 min-w-0">
          <AgentDot status={agent.status} />
          <div className="min-w-0">
            <p className="font-semibold text-gray-900 text-sm truncate">{agent.hostname}</p>
            <p className="text-xs text-gray-400">{agent.status === "online" ? "Online" : "Offline"}</p>
          </div>
        </div>
        <button onClick={onClose} className="p-1 text-gray-300 hover:text-gray-500 shrink-0"><X size={15} /></button>
      </div>

      <div className="flex border-b border-gray-100 px-4">
        {(["info", "history"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex items-center gap-1.5 py-2.5 px-1 mr-4 text-xs font-medium border-b-2 transition-colors ${tab === t ? "border-brand-500 text-brand-600" : "border-transparent text-gray-400 hover:text-gray-600"}`}
          >
            {t === "info" ? <Monitor size={11} /> : <History size={11} />}
            {t === "info" ? "Detalhes" : "Histórico"}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto p-4">
        {tab === "info" && (
          <div className="space-y-3">
            {[
              ["Cliente", (agent.raw_data as Record<string, string> | null)?.client_name],
              ["Site", (agent.raw_data as Record<string, string> | null)?.site_name],
              ["Sistema Operacional", agent.os_name],
              ["Endereço IP", agent.ip_address],
              ["Última Vez Visto", formatDate(agent.last_seen)],
              ["Sync em", formatDate(agent.synced_at)],
            ].map(([label, value]) => (
              <div key={label}>
                <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wide">{label}</p>
                <p className="text-sm text-gray-700 mt-0.5">{value || "—"}</p>
              </div>
            ))}

            <div className="grid grid-cols-2 gap-3 pt-1">
              <div className="bg-amber-50 border border-amber-100 rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-amber-600">{agent.patches_pending ?? "—"}</p>
                <p className="text-[10px] text-amber-500 mt-0.5">Patches Pendentes</p>
              </div>
              <div className="bg-red-50 border border-red-100 rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-red-500">{agent.alerts_count}</p>
                <p className="text-[10px] text-red-400 mt-0.5">Alertas</p>
              </div>
            </div>

            {integration.rmm_type === "tactical_rmm" && (
              <button
                onClick={() => onRun(agent)}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700 mt-2"
              >
                <Terminal size={14} /> Executar Comando / Script
              </button>
            )}
          </div>
        )}

        {tab === "history" && (
          <div className="space-y-2">
            {loadingRuns && <div className="flex justify-center py-6"><Loader2 size={18} className="animate-spin text-gray-300" /></div>}
            {!loadingRuns && runs.length === 0 && (
              <p className="text-xs text-gray-400 text-center py-6">Nenhuma execução registrada.</p>
            )}
            {runs.map((run) => (
              <div key={run.id} className="border border-gray-100 rounded-lg p-3">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5">
                    {run.run_type === "command" ? <Terminal size={11} className="text-gray-400" /> : <Code2 size={11} className="text-gray-400" />}
                    <span className="text-xs font-medium text-gray-700 capitalize">{run.run_type}</span>
                    <span className="text-[10px] text-gray-400">· {run.shell}</span>
                  </div>
                  <RunStatusBadge status={run.status} />
                </div>
                <pre className="text-[10px] text-gray-500 truncate font-mono mb-1">{run.body}</pre>
                {run.output && (
                  <pre className="text-[10px] bg-gray-950 text-green-400 p-2 rounded font-mono max-h-20 overflow-auto whitespace-pre-wrap">
                    {run.output}
                  </pre>
                )}
                <p className="text-[10px] text-gray-400 mt-1 flex items-center gap-1">
                  <Clock size={9} />{formatDate(run.started_at)}
                  {run.exit_code != null && <span className="ml-1">· exit: {run.exit_code}</span>}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function RmmPage() {
  const navigate = useNavigate();
  const [activeView, setActiveView] = useState<"agents" | "templates">("agents");
  const [integrations, setIntegrations] = useState<RmmIntegration[]>([]);
  const [selected, setSelected] = useState<RmmIntegration | null>(null);
  const [agents, setAgents] = useState<RmmAgent[]>([]);
  const [statusFilter, setStatusFilter] = useState<"all" | "online" | "offline">("all");
  const [selectedAgent, setSelectedAgent] = useState<RmmAgent | null>(null);
  const [runs, setRuns] = useState<RmmScriptRun[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [runModal, setRunModal] = useState<RmmAgent | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<string | null>(null);

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try { setIntegrations(await rmmApi.list()); }
    catch { toast.error("Erro ao carregar integrações RMM."); }
    finally { setLoading(false); }
  };

  const loadAgents = async (integration: RmmIntegration) => {
    setSelected(integration);
    setSelectedAgent(null);
    setAgents([]);
    setStatusFilter("all");
    try { setAgents(await rmmApi.agents(integration.id)); }
    catch { toast.error("Erro ao carregar agentes."); }
  };

  const selectAgent = async (agent: RmmAgent) => {
    setSelectedAgent(agent);
    setRuns([]);
    if (!selected) return;
    setLoadingRuns(true);
    try { setRuns(await rmmApi.scriptRuns(selected.id, agent.external_id)); }
    catch { /* silencioso */ }
    finally { setLoadingRuns(false); }
  };

  const handleSync = async (id: string) => {
    setSyncing(id);
    try {
      const result = await rmmApi.sync(id);
      toast.success(result.message);
      await load();
      const updated = integrations.find((i) => i.id === id);
      if (updated && selected?.id === id) await loadAgents(updated);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao sincronizar.";
      toast.error(msg);
    } finally { setSyncing(null); }
  };

  const handleTest = async (id: string) => {
    try {
      const result = await rmmApi.test(id);
      result.ok ? toast.success(result.message) : toast.error(result.message);
    } catch { toast.error("Erro ao testar conexão."); }
  };

  const handleRunSuccess = (run: RmmScriptRun) => {
    setRuns((prev) => [run, ...prev]);
  };

  const filtered = agents.filter((a) => statusFilter === "all" || a.status === statusFilter);
  const onlineCount = agents.filter((a) => a.status === "online").length;
  const offlineCount = agents.filter((a) => a.status === "offline").length;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Server size={24} className="text-brand-600" />
            RMM — Agentes Gerenciados
          </h1>
          <p className="text-sm text-gray-500 mt-1">Visualize e gerencie endpoints via integrações RMM.</p>
        </div>
        <button
          onClick={() => navigate("/organization?tab=integracoes")}
          className="flex items-center gap-2 px-4 py-2 border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50 text-sm"
        >
          <Settings size={15} /> Gerenciar Integrações
        </button>
      </div>

      {/* View toggle tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit mb-5">
        <button
          onClick={() => setActiveView("agents")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeView === "agents" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"}`}
        >
          <Server size={14} /> Agentes
        </button>
        <button
          onClick={() => setActiveView("templates")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeView === "templates" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"}`}
        >
          <BookOpen size={14} /> Templates de Script
        </button>
      </div>

      {/* Templates view */}
      {activeView === "templates" && <TemplatesPanel />}

      {/* Agents view */}
      {activeView === "agents" && (
        <div className={`grid gap-6 ${selectedAgent ? "grid-cols-[240px_1fr_300px]" : "grid-cols-[240px_1fr]"}`}>
          {/* Integrations sidebar */}
          <div className="space-y-3">
            {loading && <div className="flex justify-center py-8"><Loader2 size={20} className="animate-spin text-gray-400" /></div>}
            {!loading && integrations.length === 0 && (
              <div className="text-center py-10 text-gray-400 border border-dashed border-gray-200 rounded-xl">
                <Server size={32} className="mx-auto mb-2 opacity-20" />
                <p className="text-xs">Nenhuma integração configurada.</p>
                <button
                  onClick={() => navigate("/organization?tab=integracoes")}
                  className="mt-2 text-xs text-brand-600 hover:underline"
                >
                  Configurar em Organização →
                </button>
              </div>
            )}
            {integrations.map((intg) => (
              <div
                key={intg.id}
                onClick={() => loadAgents(intg)}
                className={`border rounded-xl p-4 cursor-pointer transition-all ${selected?.id === intg.id ? "border-brand-500 bg-brand-50" : "border-gray-200 bg-white hover:border-brand-300"}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm text-gray-900 truncate">{intg.name}</p>
                    <p className="text-xs text-gray-500">{RMM_TYPE_LABELS[intg.rmm_type] ?? intg.rmm_type}</p>
                  </div>
                  <ChevronRight size={14} className="text-gray-400 shrink-0 mt-0.5" />
                </div>
                <div className="flex items-center gap-3 mt-2">
                  <span className="text-xs text-gray-600"><strong>{intg.agent_count}</strong> agentes</span>
                  <StatusBadge status={intg.last_sync_status} />
                </div>
                <div className="flex gap-1 mt-2">
                  <button onClick={(e) => { e.stopPropagation(); handleTest(intg.id); }} title="Testar" className="p-1 text-gray-400 hover:text-brand-600 transition-colors">
                    <FlaskConical size={13} />
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); handleSync(intg.id); }} disabled={syncing === intg.id} title="Sincronizar" className="p-1 text-gray-400 hover:text-green-600 transition-colors disabled:opacity-50">
                    {syncing === intg.id ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                  </button>
                </div>
              </div>
            ))}
            {integrations.length > 0 && (
              <button
                onClick={() => navigate("/organization?tab=integracoes")}
                className="w-full flex items-center justify-center gap-1.5 py-2 text-xs text-gray-400 hover:text-brand-600 border border-dashed border-gray-200 rounded-xl hover:border-brand-300 transition-colors"
              >
                <Settings size={11} /> Gerenciar integrações
              </button>
            )}
          </div>

          {/* Agent table */}
          <div className="bg-white border border-gray-200 rounded-xl flex flex-col min-h-0">
            {!selected ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-300 py-20">
                <Server size={48} className="mb-3 opacity-20" />
                <p className="text-sm">Selecione uma integração para ver os agentes.</p>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-4 px-5 py-3 border-b border-gray-100">
                  <h2 className="font-semibold text-gray-800 text-sm flex-1">{selected.name}</h2>
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1 text-xs text-green-600">
                      <Wifi size={12} /><strong>{onlineCount}</strong> online
                    </span>
                    <span className="flex items-center gap-1 text-xs text-gray-400">
                      <WifiOff size={12} /><strong>{offlineCount}</strong> offline
                    </span>
                    {agents.some((a) => (a.patches_pending ?? 0) > 0) && (
                      <span className="flex items-center gap-1 text-xs text-amber-600">
                        <AlertTriangle size={12} />
                        <strong>{agents.reduce((s, a) => s + (a.patches_pending ?? 0), 0)}</strong> patches
                      </span>
                    )}
                  </div>
                  <div className="flex gap-1 bg-gray-100 rounded-lg p-0.5">
                    {(["all", "online", "offline"] as const).map((f) => (
                      <button
                        key={f}
                        onClick={() => setStatusFilter(f)}
                        className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${statusFilter === f ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"}`}
                      >
                        {f === "all" ? "Todos" : f === "online" ? "Online" : "Offline"}
                      </button>
                    ))}
                  </div>
                </div>

                {filtered.length === 0 ? (
                  <p className="text-sm text-gray-400 text-center py-10">
                    {agents.length === 0 ? "Nenhum agente sincronizado." : "Nenhum agente com este filtro."}
                  </p>
                ) : (
                  <div className="overflow-auto flex-1">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-left text-gray-400 border-b border-gray-100">
                          <th className="pb-2 px-5 pt-3 font-medium">Status</th>
                          <th className="pb-2 pt-3 font-medium">Hostname</th>
                          <th className="pb-2 pt-3 font-medium">Site / Cliente</th>
                          <th className="pb-2 pt-3 font-medium">IP</th>
                          <th className="pb-2 pt-3 font-medium">SO</th>
                          <th className="pb-2 pt-3 font-medium text-center">Patches</th>
                          <th className="pb-2 pt-3 font-medium text-center">Alertas</th>
                          <th className="pb-2 pt-3 font-medium text-center">Ações</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filtered.map((a) => (
                          <tr
                            key={a.id}
                            onClick={() => selectAgent(a)}
                            className={`border-b border-gray-50 cursor-pointer transition-colors ${selectedAgent?.id === a.id ? "bg-brand-50" : "hover:bg-gray-50"}`}
                          >
                            <td className="py-2 px-5"><AgentDot status={a.status} /></td>
                            <td className="py-2 font-medium text-gray-800">{a.hostname}</td>
                            <td className="py-2 text-gray-500 text-xs">
                              {(a.raw_data as Record<string, string> | null)?.client_name
                                ? <span className="flex flex-col leading-tight">
                                    <span className="font-medium text-gray-700">{(a.raw_data as Record<string, string>).client_name}</span>
                                    {(a.raw_data as Record<string, string>).site_name && (
                                      <span className="text-[10px] text-gray-400">{(a.raw_data as Record<string, string>).site_name}</span>
                                    )}
                                  </span>
                                : <span className="text-gray-300">—</span>}
                            </td>
                            <td className="py-2 text-gray-500">{a.ip_address || "—"}</td>
                            <td className="py-2 text-gray-500 max-w-[130px] truncate">{a.os_name || "—"}</td>
                            <td className="py-2 text-center">
                              {a.patches_pending != null
                                ? <span className={`font-medium ${a.patches_pending > 0 ? "text-amber-600" : "text-gray-400"}`}>{a.patches_pending}</span>
                                : <span className="text-gray-300">—</span>}
                            </td>
                            <td className="py-2 text-center">
                              {a.alerts_count > 0
                                ? <span className="text-red-500 font-medium">{a.alerts_count}</span>
                                : <span className="text-gray-300">0</span>}
                            </td>
                            <td className="py-2 text-center">
                              {selected.rmm_type === "tactical_rmm" && (
                                <button
                                  onClick={(e) => { e.stopPropagation(); setRunModal(a); }}
                                  title="Executar comando/script"
                                  className="p-1 text-gray-300 hover:text-brand-600 transition-colors"
                                >
                                  <Terminal size={13} />
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Agent detail panel */}
          {selectedAgent && selected && (
            <AgentDetail
              agent={selectedAgent}
              integration={selected}
              onRun={(agent) => setRunModal(agent)}
              onClose={() => setSelectedAgent(null)}
              runs={runs}
              loadingRuns={loadingRuns}
            />
          )}
        </div>
      )}

      {/* Run Modal */}
      {runModal && selected && (
        <RunModal
          integration={selected}
          agent={runModal}
          onClose={() => setRunModal(null)}
          onSuccess={handleRunSuccess}
        />
      )}
    </div>
  );
}
