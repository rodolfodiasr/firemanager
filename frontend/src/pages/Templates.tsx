import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  BookMarked, Search, ChevronRight, Play, Send, X, Plus,
  Trash2, Loader2, Terminal,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { devicesApi } from "../api/devices";
import { templatesApi } from "../api/templates";
import { operationsApi } from "../api/operations";
import type { RuleTemplate, TemplateParameter } from "../types/template";
import type { Device } from "../types/device";
import { useAuthStore } from "../store/authStore";

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderCommands(commands: string[], params: Record<string, string>): string[] {
  const expanded: Record<string, string> = {};
  for (const [key, value] of Object.entries(params)) {
    expanded[key] = value;
    expanded[`${key}_dashes`] = value.replace(/\./g, "-").replace(/ /g, "-").toLowerCase();
    expanded[`${key}_slug`] = value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }
  return commands.map((cmd) =>
    cmd.replace(/\{(\w+)\}/g, (_, k) => expanded[k] ?? `{${k}}`)
  );
}

const VENDOR_LABELS: Record<string, string> = {
  sonicwall: "SonicWall",
  fortinet: "Fortinet",
  pfsense: "pfSense",
};

// ── Parameter Form ────────────────────────────────────────────────────────────
function ParamField({
  param, value, onChange,
}: {
  param: TemplateParameter;
  value: string;
  onChange: (v: string) => void;
}) {
  if (param.type === "select") {
    return (
      <select
        value={value || param.default || ""}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
      >
        <option value="">Selecione...</option>
        {(param.options ?? []).map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    );
  }
  if (param.type === "boolean") {
    return (
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={value === "true"}
          onChange={(e) => onChange(e.target.checked ? "true" : "false")}
          className="h-4 w-4 rounded border-gray-300 text-brand-600"
        />
        <span className="text-sm text-gray-700">{param.label}</span>
      </label>
    );
  }
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={param.placeholder ?? ""}
      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
    />
  );
}

// ── Template Modal ─────────────────────────────────────────────────────────────
function TemplateModal({
  template, onClose,
}: {
  template: RuleTemplate;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const [deviceId, setDeviceId] = useState("");
  const [params, setParams] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    template.parameters.forEach((p) => { init[p.key] = p.default ?? ""; });
    return init;
  });

  const { data: devices = [] } = useQuery({ queryKey: ["devices"], queryFn: devicesApi.list });

  const preview = useMemo(() => renderCommands(template.ssh_commands, params), [template.ssh_commands, params]);

  const createMutation = useMutation({
    mutationFn: (action: "execute" | "review") =>
      operationsApi.createDirectSSH({
        device_id: deviceId,
        description: `[Template] ${template.name}`,
        ssh_commands: preview,
      }).then(async (op) => {
        if (action === "execute") {
          return operationsApi.execute(op.id);
        } else {
          return operationsApi.submitForReview(op.id);
        }
      }),
    onSuccess: (_data, action) => {
      onClose();
      if (action === "execute") {
        toast.success("Template executado! Verifique o Histórico.");
      } else {
        toast.success("Enviado para revisão N2.");
      }
      navigate("/audit");
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Erro ao executar template.");
    },
  });

  const missingRequired = template.parameters
    .filter((p) => p.required && !params[p.key]?.trim())
    .map((p) => p.label);

  const canSubmit = deviceId && missingRequired.length === 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-gray-200 shrink-0">
          <div>
            <h2 className="text-base font-semibold text-gray-900">{template.name}</h2>
            <p className="text-sm text-gray-500 mt-0.5">{template.description}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 ml-4 shrink-0">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* Device */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Dispositivo</label>
            <select
              value={deviceId}
              onChange={(e) => setDeviceId(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">Selecione o dispositivo...</option>
              {devices.map((d: Device) => (
                <option key={d.id} value={d.id}>
                  {d.name} — {d.vendor} ({d.host})
                </option>
              ))}
            </select>
          </div>

          {/* Parameters */}
          {template.parameters.length > 0 && (
            <div className="space-y-4">
              <p className="text-sm font-medium text-gray-700">Parâmetros</p>
              {template.parameters.map((p) => (
                <div key={p.key}>
                  {p.type !== "boolean" && (
                    <label className="block text-sm text-gray-600 mb-1">
                      {p.label}
                      {p.required && <span className="text-red-500 ml-0.5">*</span>}
                    </label>
                  )}
                  <ParamField
                    param={p}
                    value={params[p.key] ?? ""}
                    onChange={(v) => setParams((prev) => ({ ...prev, [p.key]: v }))}
                  />
                </div>
              ))}
            </div>
          )}

          {/* Live preview */}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Preview de comandos ({preview.length})
            </p>
            <pre className="bg-gray-900 text-green-300 rounded-lg p-3 text-xs font-mono overflow-auto max-h-48 whitespace-pre-wrap">
              {preview.join("\n")}
            </pre>
          </div>

          {missingRequired.length > 0 && (
            <p className="text-xs text-red-500">
              Preencha os campos obrigatórios: {missingRequired.join(", ")}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-3 px-6 py-4 border-t border-gray-200 shrink-0">
          <button
            onClick={() => createMutation.mutate("execute")}
            disabled={!canSubmit || createMutation.isPending}
            className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {createMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
            Executar
          </button>
          <button
            onClick={() => createMutation.mutate("review")}
            disabled={!canSubmit || createMutation.isPending}
            className="flex items-center gap-2 px-5 py-2.5 bg-yellow-500 text-white text-sm font-medium rounded-lg hover:bg-yellow-600 disabled:opacity-50"
          >
            <Send size={15} />
            Enviar para N2
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Create Template Modal ─────────────────────────────────────────────────────
function CreateTemplateModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    slug: "", name: "", description: "", category: "",
    vendor: "sonicwall", firmware_pattern: "7.*", ssh_commands: "",
  });

  const createMutation = useMutation({
    mutationFn: () =>
      templatesApi.create({
        ...form,
        ssh_commands: form.ssh_commands.split("\n").map((l) => l.trim()).filter(Boolean),
        parameters: [],
      }),
    onSuccess: () => {
      toast.success("Template criado!");
      qc.invalidateQueries({ queryKey: ["templates"] });
      onClose();
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Erro ao criar template.");
    },
  });

  const f = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-lg overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-900">Novo Template</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>
        <div className="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto">
          {[
            { key: "slug", label: "Slug (único, sem espaços)", placeholder: "minha-empresa-regra-x" },
            { key: "name", label: "Nome", placeholder: "Descrição curta" },
            { key: "description", label: "Descrição", placeholder: "O que este template faz" },
            { key: "category", label: "Categoria", placeholder: "ex: Serviços de Segurança" },
          ].map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
              <input type="text" value={(form as Record<string, string>)[key]} onChange={f(key)}
                placeholder={placeholder}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
          ))}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Vendor</label>
              <select value={form.vendor} onChange={f("vendor")}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                <option value="sonicwall">SonicWall</option>
                <option value="fortinet">Fortinet</option>
                <option value="pfsense">pfSense</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Firmware (glob)</label>
              <input type="text" value={form.firmware_pattern} onChange={f("firmware_pattern")}
                placeholder="7.* ou *"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Comandos SSH <span className="font-normal text-gray-400">(um por linha)</span>
            </label>
            <textarea value={form.ssh_commands} onChange={f("ssh_commands")} rows={8} spellCheck={false}
              placeholder={"gateway-antivirus\nenable\nexit\ncommit"}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
            <p className="text-xs text-gray-400 mt-1">Use {"{"}param{"}"} para parâmetros dinâmicos (configure via API após criação).</p>
          </div>
        </div>
        <div className="px-6 py-4 border-t border-gray-200 flex gap-3">
          <button onClick={() => createMutation.mutate()} disabled={!form.slug || !form.name || !form.ssh_commands || createMutation.isPending}
            className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50">
            {createMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
            Criar Template
          </button>
          <button onClick={onClose} className="px-4 py-2.5 text-sm text-gray-500 border border-gray-300 rounded-lg hover:bg-gray-50">Cancelar</button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function Templates() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.role === "admin";
  const qc = useQueryClient();

  const [search, setSearch] = useState("");
  const [vendorFilter, setVendorFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [selected, setSelected] = useState<RuleTemplate | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const { data: templates = [], isLoading } = useQuery({
    queryKey: ["templates", vendorFilter, categoryFilter],
    queryFn: () => templatesApi.list({ vendor: vendorFilter || undefined, category: categoryFilter || undefined }),
  });

  const deleteMutation = useMutation({
    mutationFn: (slug: string) => templatesApi.delete(slug),
    onSuccess: () => {
      toast.success("Template removido.");
      qc.invalidateQueries({ queryKey: ["templates"] });
    },
    onError: () => toast.error("Erro ao remover template."),
  });

  const vendors = Array.from(new Set(templates.map((t) => t.vendor)));
  const categories = Array.from(new Set(templates.map((t) => t.category)));

  const filtered = templates.filter((t) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q) || t.category.toLowerCase().includes(q);
  });

  return (
    <PageWrapper title="Templates de Regras">
      {selected && <TemplateModal template={selected} onClose={() => setSelected(null)} />}
      {showCreate && <CreateTemplateModal onClose={() => setShowCreate(false)} />}

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar templates..."
            className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <select value={vendorFilter} onChange={(e) => setVendorFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
          <option value="">Todos os vendors</option>
          {vendors.map((v) => <option key={v} value={v}>{VENDOR_LABELS[v] ?? v}</option>)}
        </select>
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
          <option value="">Todas as categorias</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        {isAdmin && (
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700">
            <Plus size={15} />
            Novo Template
          </button>
        )}
      </div>

      {isLoading && <div className="py-10 text-center text-gray-400">Carregando templates...</div>}

      {!isLoading && filtered.length === 0 && (
        <div className="py-14 text-center text-gray-400">
          <BookMarked size={36} className="mx-auto mb-3 text-gray-300" />
          <p className="text-sm">Nenhum template encontrado.</p>
        </div>
      )}

      {/* Template grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((t) => (
          <div key={t.slug}
            className="bg-white border border-gray-200 rounded-xl p-5 hover:border-brand-300 hover:shadow-sm transition-all group flex flex-col gap-3">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <Terminal size={16} className="text-brand-600 shrink-0" />
                <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">{t.category}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  t.is_builtin ? "bg-blue-50 text-blue-600" : "bg-purple-50 text-purple-600"
                }`}>
                  {t.is_builtin ? "Embutido" : "Custom"}
                </span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 font-medium">
                  {VENDOR_LABELS[t.vendor] ?? t.vendor}
                </span>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-900">{t.name}</h3>
              <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{t.description}</p>
            </div>

            <div className="flex items-center gap-2 text-xs text-gray-400">
              <span>{t.ssh_commands.length} cmds</span>
              {t.parameters.length > 0 && <span>· {t.parameters.length} param(s)</span>}
              <span>· fw {t.firmware_pattern}</span>
            </div>

            <div className="flex gap-2 mt-auto pt-1">
              <button onClick={() => setSelected(t)}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-brand-600 text-white text-xs font-medium rounded-lg hover:bg-brand-700">
                <ChevronRight size={13} />
                Usar template
              </button>
              {isAdmin && !t.is_builtin && (
                <button onClick={() => {
                  if (confirm(`Remover "${t.name}"?`)) deleteMutation.mutate(t.slug);
                }}
                  className="px-3 py-2 text-red-500 border border-red-200 rounded-lg hover:bg-red-50 text-xs">
                  <Trash2 size={13} />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </PageWrapper>
  );
}
