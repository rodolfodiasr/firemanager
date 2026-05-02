import { useState, useMemo, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus, Shield, Route, Network, Layers, LayoutGrid, CheckSquare, Square,
  Layers as LayersIcon, FolderPlus, FolderOpen, Pencil, Trash2, Sparkles,
  Loader2, AlertCircle, ChevronRight, BookMarked, Search, Play, Send, X,
  Terminal, Globe, Server, ChevronDown, Tag, AlertTriangle, Check,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { DeviceCard } from "../components/devices/DeviceCard";
import { AddDeviceModal } from "../components/devices/AddDeviceModal";
import { EditDeviceModal } from "../components/devices/EditDeviceModal";
import { BulkOperationModal } from "../components/devices/BulkOperationModal";
import { GroupModal } from "../components/device_groups/GroupModal";
import { ConfirmModal } from "../components/shared/ConfirmModal";
import { EmptyState } from "../components/shared/EmptyState";
import { useDevices } from "../hooks/useDevices";
import { deviceGroupsApi } from "../api/device_groups";
import { devicesApi } from "../api/devices";
import { templatesApi } from "../api/templates";
import { operationsApi } from "../api/operations";
import { variablesApi } from "../api/variables";
import { useAuthStore } from "../store/authStore";
import type { Device, DeviceCategory, DeviceCreate } from "../types/device";
import type { DeviceGroup } from "../types/device_group";
import type { RuleTemplate, TemplateParameter } from "../types/template";
import type { TenantVariable, DeviceVariable, VariableType, VariableFormData } from "../types/variable";
import { VARIABLE_TYPE_LABELS } from "../types/variable";

type OuterTab = "dispositivos" | "grupos" | "templates" | "variaveis";
type FilterCategory = DeviceCategory | "all";

// ── Variables helpers ─────────────────────────────────────────────────────────

const TYPE_COLORS: Record<VariableType, string> = {
  string:    "bg-gray-100 text-gray-600",
  network:   "bg-blue-100 text-blue-700",
  ip:        "bg-indigo-100 text-indigo-700",
  port:      "bg-orange-100 text-orange-700",
  interface: "bg-purple-100 text-purple-700",
  zone:      "bg-teal-100 text-teal-700",
  hostname:  "bg-pink-100 text-pink-700",
  gateway:   "bg-amber-100 text-amber-700",
};

function TypeBadge({ type }: { type: VariableType }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${TYPE_COLORS[type]}`}>
      {VARIABLE_TYPE_LABELS[type]}
    </span>
  );
}

const EMPTY_FORM: VariableFormData = { name: "", value: "", variable_type: "string", description: "" };

function VarModal({ initial = EMPTY_FORM, onSave, onClose, isLoading, title, nameReadOnly }: {
  initial?: VariableFormData; onSave: (d: VariableFormData) => void; onClose: () => void;
  isLoading: boolean; title: string; nameReadOnly?: boolean;
}) {
  const [form, setForm] = useState<VariableFormData>(initial);
  const set = (k: keyof VariableFormData, v: string) => setForm((f) => ({ ...f, [k]: v }));
  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h3 className="text-base font-semibold text-gray-900">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Nome <span className="text-gray-400 font-normal">(use como <code className="bg-gray-100 px-1 rounded">{`{{nome}}`}</code>)</span>
            </label>
            <input value={form.name} onChange={(e) => set("name", e.target.value)} disabled={nameReadOnly}
              placeholder="rede_local"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-gray-50 font-mono" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Tipo</label>
            <select value={form.variable_type} onChange={(e) => set("variable_type", e.target.value as VariableType)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
              {(Object.keys(VARIABLE_TYPE_LABELS) as VariableType[]).map((t) => (
                <option key={t} value={t}>{VARIABLE_TYPE_LABELS[t]}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Valor</label>
            <input value={form.value} onChange={(e) => set("value", e.target.value)}
              placeholder={form.variable_type === "network" ? "192.168.1.0/24" : form.variable_type === "port" ? "443" : "valor"}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Descrição <span className="text-gray-400 font-normal">(opcional)</span></label>
            <input value={form.description} onChange={(e) => set("description", e.target.value)}
              placeholder="Rede local da filial principal"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
        </div>
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">Cancelar</button>
          <button onClick={() => onSave(form)} disabled={isLoading || !form.name.trim() || !form.value.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 rounded-lg disabled:opacity-50 flex items-center gap-2">
            {isLoading ? <span className="animate-spin border-2 border-white border-t-transparent rounded-full w-3 h-3" /> : <Check size={14} />}
            Salvar
          </button>
        </div>
      </div>
    </div>
  );
}

function VarRow({ name, value, type, description, badge, onEdit, onDelete }: {
  name: string; value: string; type: VariableType; description?: string | null;
  badge?: React.ReactNode; onEdit: () => void; onDelete: () => void;
}) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 rounded-lg group">
      <Tag size={14} className="text-gray-400 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <code className="text-sm font-mono font-semibold text-gray-800">{`{{${name}}}`}</code>
          <TypeBadge type={type} />
          {badge}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-sm text-gray-600 font-mono truncate">{value}</span>
          {description && <span className="text-xs text-gray-400 truncate">— {description}</span>}
        </div>
      </div>
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <button onClick={onEdit} className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-brand-50 rounded-md"><Pencil size={13} /></button>
        <button onClick={onDelete} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md"><Trash2 size={13} /></button>
      </div>
    </div>
  );
}

// ── Templates helpers ─────────────────────────────────────────────────────────

function renderCommands(commands: string[], params: Record<string, string>): string[] {
  const expanded: Record<string, string> = {};
  for (const [key, value] of Object.entries(params)) {
    expanded[key] = value;
    expanded[`${key}_dashes`] = value.replace(/\./g, "-").replace(/ /g, "-").toLowerCase();
    expanded[`${key}_slug`] = value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }
  return commands.map((cmd) => cmd.replace(/\{(\w+)\}/g, (_, k) => expanded[k] ?? `{${k}}`));
}

const VENDOR_LABELS: Record<string, string> = { sonicwall: "SonicWall", fortinet: "Fortinet", pfsense: "pfSense" };

function ParamField({ param, value, onChange }: { param: TemplateParameter; value: string; onChange: (v: string) => void }) {
  if (param.type === "select") {
    return (
      <select value={value || param.default || ""} onChange={(e) => onChange(e.target.value)}
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
        <option value="">Selecione...</option>
        {(param.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  if (param.type === "boolean") {
    return (
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={value === "true"} onChange={(e) => onChange(e.target.checked ? "true" : "false")}
          className="h-4 w-4 rounded border-gray-300 text-brand-600" />
        <span className="text-sm text-gray-700">{param.label}</span>
      </label>
    );
  }
  return (
    <input type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder={param.placeholder ?? ""}
      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500" />
  );
}

function TemplateModal({ template, onClose, initialParams, initialDeviceId, parentOperationId }: {
  template: RuleTemplate; onClose: () => void;
  initialParams?: Record<string, string>; initialDeviceId?: string; parentOperationId?: string;
}) {
  const navigate = useNavigate();
  const [deviceId, setDeviceId] = useState(initialDeviceId ?? "");
  const [params, setParams] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    template.parameters.forEach((p) => { init[p.key] = initialParams?.[p.key] ?? p.default ?? ""; });
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
        template_slug: template.slug,
        template_params: params,
        ...(parentOperationId ? { parent_operation_id: parentOperationId } : {}),
      }).then(async (op) => {
        if (action === "execute") return operationsApi.execute(op.id);
        else return operationsApi.submitForReview(op.id);
      }),
    onSuccess: (_data, action) => {
      onClose();
      if (action === "execute") toast.success("Template executado! Verifique o Histórico.");
      else toast.success("Enviado para revisão N2.");
      navigate("/audit");
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Erro ao executar template.");
    },
  });

  const missingRequired = template.parameters.filter((p) => p.required && !params[p.key]?.trim()).map((p) => p.label);
  const canSubmit = deviceId && missingRequired.length === 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        <div className="flex items-start justify-between px-6 py-4 border-b border-gray-200 shrink-0">
          <div>
            <h2 className="text-base font-semibold text-gray-900">{template.name}</h2>
            <p className="text-sm text-gray-500 mt-0.5">{template.description}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 ml-4 shrink-0"><X size={20} /></button>
        </div>
        {parentOperationId && (
          <div className="flex items-center gap-2 px-6 py-2 bg-amber-50 border-b border-amber-200">
            <Pencil size={13} className="text-amber-600 shrink-0" />
            <p className="text-xs text-amber-800 font-medium">Editando operação anterior — ajuste os parâmetros e execute novamente.</p>
          </div>
        )}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Dispositivo</label>
            <select value={deviceId} onChange={(e) => setDeviceId(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
              <option value="">Selecione o dispositivo...</option>
              {devices.map((d: Device) => (
                <option key={d.id} value={d.id}>{d.name} — {d.vendor} ({d.host})</option>
              ))}
            </select>
          </div>
          {template.parameters.length > 0 && (
            <div className="space-y-4">
              <p className="text-sm font-medium text-gray-700">Parâmetros</p>
              {template.parameters.map((p) => (
                <div key={p.key}>
                  {p.type !== "boolean" && (
                    <label className="block text-sm text-gray-600 mb-1">
                      {p.label}{p.required && <span className="text-red-500 ml-0.5">*</span>}
                    </label>
                  )}
                  <ParamField param={p} value={params[p.key] ?? ""} onChange={(v) => setParams((prev) => ({ ...prev, [p.key]: v }))} />
                </div>
              ))}
            </div>
          )}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Preview de comandos ({preview.length})</p>
            <pre className="bg-gray-900 text-green-300 rounded-lg p-3 text-xs font-mono overflow-auto max-h-48 whitespace-pre-wrap">{preview.join("\n")}</pre>
          </div>
          {missingRequired.length > 0 && (
            <p className="text-xs text-red-500">Preencha os campos obrigatórios: {missingRequired.join(", ")}</p>
          )}
        </div>
        <div className="flex gap-3 px-6 py-4 border-t border-gray-200 shrink-0">
          <button onClick={() => createMutation.mutate("execute")} disabled={!canSubmit || createMutation.isPending}
            className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50">
            {createMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
            Executar
          </button>
          <button onClick={() => createMutation.mutate("review")} disabled={!canSubmit || createMutation.isPending}
            className="flex items-center gap-2 px-5 py-2.5 bg-yellow-500 text-white text-sm font-medium rounded-lg hover:bg-yellow-600 disabled:opacity-50">
            <Send size={15} /> Enviar para N2
          </button>
        </div>
      </div>
    </div>
  );
}

function CreateTemplateModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    slug: "", name: "", description: "", category: "",
    vendor: "sonicwall", firmware_pattern: "7.*", ssh_commands: "",
  });
  const createMutation = useMutation({
    mutationFn: () => templatesApi.create({
      ...form,
      ssh_commands: form.ssh_commands.split("\n").map((l) => l.trim()).filter(Boolean),
      parameters: [],
    }),
    onSuccess: () => { toast.success("Template criado!"); qc.invalidateQueries({ queryKey: ["templates"] }); onClose(); },
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
              <input type="text" value={(form as Record<string, string>)[key]} onChange={f(key)} placeholder={placeholder}
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
              <input type="text" value={form.firmware_pattern} onChange={f("firmware_pattern")} placeholder="7.* ou *"
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
            <p className="text-xs text-gray-400 mt-1">Use {"{"}param{"}"} para parâmetros dinâmicos.</p>
          </div>
        </div>
        <div className="px-6 py-4 border-t border-gray-200 flex gap-3">
          <button onClick={() => createMutation.mutate()}
            disabled={!form.slug || !form.name || !form.ssh_commands || createMutation.isPending}
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

// ── Grupos helpers ────────────────────────────────────────────────────────────

const GROUP_CATEGORY_ICON: Record<string, React.ElementType> = {
  firewall: Shield, router: Route, switch: Network, l3_switch: Layers,
};
const GROUP_CATEGORY_LABEL: Record<string, string> = {
  firewall: "Firewall", router: "Roteador", switch: "Switch", l3_switch: "Switch L3",
};

function CategoryBadge({ category, count }: { category: string; count: number }) {
  const Icon = GROUP_CATEGORY_ICON[category] ?? Layers;
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-gray-100 text-gray-600 rounded-full px-2 py-0.5">
      <Icon size={10} />{GROUP_CATEGORY_LABEL[category] ?? category} <span className="font-medium">{count}</span>
    </span>
  );
}

function ApplyPanel({ group, onDone }: { group: DeviceGroup; onDone: () => void }) {
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const applyMut = useMutation({
    mutationFn: () => deviceGroupsApi.createBulkJob(group.id, input),
    onSuccess: () => { onDone(); navigate("/audit"); },
  });
  return (
    <div className="mt-3 pt-3 border-t border-gray-100">
      <textarea value={input} onChange={(e) => setInput(e.target.value)} rows={2} autoFocus
        placeholder="Ex: Bloquear portas não utilizadas e aplicar VLAN 10"
        className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
      {applyMut.isError && (
        <div className="flex items-center gap-1 text-red-600 text-xs mt-1">
          <AlertCircle size={11} />
          {(applyMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao iniciar operação."}
        </div>
      )}
      <div className="flex justify-end gap-2 mt-2">
        <button onClick={onDone} className="text-xs text-gray-500 hover:text-gray-700">Cancelar</button>
        <button onClick={() => applyMut.mutate()} disabled={input.trim().length < 5 || applyMut.isPending}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50">
          {applyMut.isPending ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} />}
          {applyMut.isPending ? "Processando IA..." : "Aplicar"}
        </button>
      </div>
    </div>
  );
}

function GroupCard({ group, onEdit, onDelete, canWrite }: {
  group: DeviceGroup; onEdit: (g: DeviceGroup) => void; onDelete: (id: string) => void; canWrite: boolean;
}) {
  const [applying, setApplying] = useState(false);
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="bg-brand-50 text-brand-600 p-2 rounded-lg shrink-0"><FolderOpen size={16} /></div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-gray-900 truncate">{group.name}</h3>
            {group.description && <p className="text-xs text-gray-400 truncate">{group.description}</p>}
          </div>
        </div>
        {canWrite && (
          <div className="flex items-center gap-1 shrink-0 ml-2">
            <button onClick={() => onEdit(group)} className="p-1.5 text-gray-400 hover:text-gray-600 rounded" title="Editar"><Pencil size={13} /></button>
            <button onClick={() => onDelete(group.id)} className="p-1.5 text-gray-400 hover:text-red-500 rounded" title="Remover"><Trash2 size={13} /></button>
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 flex-wrap mb-1">
        <span className="text-xs font-medium text-gray-500">{group.device_count} dispositivo{group.device_count !== 1 ? "s" : ""}</span>
        {Object.entries(group.category_counts).map(([cat, cnt]) => (
          <CategoryBadge key={cat} category={cat} count={cnt} />
        ))}
      </div>
      {canWrite && (
        applying
          ? <ApplyPanel group={group} onDone={() => setApplying(false)} />
          : (
            <button onClick={() => setApplying(true)} className="flex items-center gap-1.5 text-xs text-brand-600 hover:text-brand-700 font-medium mt-3">
              <Sparkles size={12} /> Aplicar operação neste grupo <ChevronRight size={12} />
            </button>
          )
      )}
    </div>
  );
}

function EditGroupWrapper({ groupId, onClose }: { groupId: string; onClose: () => void }) {
  const { data: detail, isLoading } = useQuery({
    queryKey: ["device-groups", groupId],
    queryFn: () => deviceGroupsApi.get(groupId),
  });
  if (isLoading || !detail) return null;
  return <GroupModal isOpen group={detail} onClose={onClose} />;
}

// ── Tab components ────────────────────────────────────────────────────────────

const FILTER_TABS: { key: FilterCategory; label: string; icon: React.ElementType }[] = [
  { key: "all",       label: "Todos",     icon: LayoutGrid },
  { key: "firewall",  label: "Firewall",  icon: Shield },
  { key: "router",    label: "Roteador",  icon: Route },
  { key: "switch",    label: "Switch",    icon: Network },
  { key: "l3_switch", label: "Switch L3", icon: Layers },
];

function DevicesTab() {
  const { devices, isLoading, create, update, remove, healthCheck } = useDevices();
  const [showAdd, setShowAdd]       = useState(false);
  const [editDevice, setEditDevice] = useState<Device | null>(null);
  const [deleteId, setDeleteId]     = useState<string | null>(null);
  const [filter, setFilter]         = useState<FilterCategory>("all");
  const [selectMode, setSelectMode]   = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showBulk, setShowBulk]       = useState(false);
  const [showSaveGroup, setShowSaveGroup] = useState(false);

  const filtered = filter === "all" ? devices : devices.filter((d) => (d.category ?? "firewall") === filter);
  const countByCategory = (cat: DeviceCategory) => devices.filter((d) => (d.category ?? "firewall") === cat).length;

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => { const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next; });
  };
  const toggleSelectAll = () => {
    if (selectedIds.size === filtered.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(filtered.map((d) => d.id)));
  };
  const exitSelectMode = () => { setSelectMode(false); setSelectedIds(new Set()); };
  const selectedDevices = devices.filter((d) => selectedIds.has(d.id));

  return (
    <>
      <div className="flex items-center gap-1 mb-6 bg-gray-100 p-1 rounded-xl w-fit">
        {FILTER_TABS.map(({ key, label, icon: Icon }) => {
          const count = key === "all" ? devices.length : countByCategory(key as DeviceCategory);
          return (
            <button key={key} onClick={() => setFilter(key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                filter === key ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              }`}>
              <Icon size={14} />
              {label}
              {count > 0 && (
                <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                  filter === key ? "bg-brand-100 text-brand-700" : "bg-gray-200 text-gray-500"
                }`}>{count}</span>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-3">
          <p className="text-sm text-gray-500">
            {filtered.length} dispositivo(s){filter !== "all" ? ` · ${FILTER_TABS.find(t => t.key === filter)?.label}` : ""}
          </p>
          {filtered.length >= 2 && (
            <button onClick={() => { selectMode ? exitSelectMode() : setSelectMode(true); }}
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-colors ${
                selectMode ? "bg-brand-50 border-brand-300 text-brand-700" : "border-gray-200 text-gray-500 hover:border-gray-300"
              }`}>
              {selectMode ? <CheckSquare size={13} /> : <Square size={13} />}
              {selectMode ? "Cancelar seleção" : "Selecionar vários"}
            </button>
          )}
          {selectMode && filtered.length > 0 && (
            <button onClick={toggleSelectAll} className="text-xs text-brand-600 hover:underline">
              {selectedIds.size === filtered.length ? "Desmarcar todos" : "Selecionar todos"}
            </button>
          )}
        </div>
        <div className="flex items-center gap-2">
          {selectMode && selectedIds.size >= 2 && (
            <>
              <button onClick={() => setShowSaveGroup(true)}
                className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-800 text-white text-sm rounded-lg transition-colors font-medium">
                <FolderPlus size={16} /> Salvar como grupo
              </button>
              <button onClick={() => setShowBulk(true)}
                className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm rounded-lg transition-colors font-medium">
                <LayersIcon size={16} /> Operação em lote ({selectedIds.size})
              </button>
            </>
          )}
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 transition-colors">
            <Plus size={16} /> Adicionar
          </button>
        </div>
      </div>

      {selectMode && selectedIds.size < 2 && (
        <p className="text-xs text-gray-400 mb-3">Selecione pelo menos 2 dispositivos para aplicar uma operação em lote.</p>
      )}

      {isLoading ? (
        <p className="text-sm text-gray-400">Carregando...</p>
      ) : filtered.length === 0 ? (
        <EmptyState
          title={filter === "all" ? "Nenhum dispositivo cadastrado" : `Nenhum ${FILTER_TABS.find(t => t.key === filter)?.label} cadastrado`}
          description="Adicione um dispositivo para começar."
          action={<button onClick={() => setShowAdd(true)} className="px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700">Adicionar dispositivo</button>}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((device) => (
            <div key={device.id} className="relative">
              {selectMode && (
                <button onClick={() => toggleSelect(device.id)}
                  className={`absolute top-2 right-2 z-10 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                    selectedIds.has(device.id) ? "bg-brand-600 border-brand-600" : "bg-white border-gray-300 hover:border-brand-400"
                  }`}>
                  {selectedIds.has(device.id) && (
                    <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 12 12">
                      <path d="M10 3L5 8.5 2 5.5" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round"/>
                    </svg>
                  )}
                </button>
              )}
              <div className={selectedIds.has(device.id) ? "ring-2 ring-brand-500 rounded-xl" : ""}
                onClick={selectMode ? () => toggleSelect(device.id) : undefined}>
                <DeviceCard
                  device={device}
                  onSelect={selectMode ? () => {} : () => {}}
                  onHealthCheck={selectMode ? () => {} : healthCheck}
                  onEdit={selectMode ? () => {} : setEditDevice}
                  onDelete={selectMode ? () => {} : (id) => setDeleteId(id)}
                  isSelected={selectedIds.has(device.id)}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      <AddDeviceModal isOpen={showAdd} onClose={() => setShowAdd(false)} onSubmit={async (data: DeviceCreate) => { await create(data); setShowAdd(false); }} />
      <GroupModal isOpen={showSaveGroup} initialDeviceIds={[...selectedIds]} onClose={() => setShowSaveGroup(false)} />
      <BulkOperationModal isOpen={showBulk} devices={selectedDevices} onClose={() => setShowBulk(false)} />
      <EditDeviceModal isOpen={!!editDevice} device={editDevice} onClose={() => setEditDevice(null)} onSubmit={update} />
      <ConfirmModal
        isOpen={!!deleteId} title="Remover dispositivo"
        description="Tem certeza que deseja remover este dispositivo? Esta ação não pode ser desfeita."
        danger onConfirm={() => { if (deleteId) remove(deleteId); setDeleteId(null); }}
        onCancel={() => setDeleteId(null)} confirmLabel="Remover"
      />
    </>
  );
}

function GruposTab() {
  const tenantRole = useAuthStore((s) => s.tenantRole);
  const canWrite = tenantRole !== "readonly";
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editGroup, setEditGroup] = useState<DeviceGroup | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { data: groups = [], isLoading } = useQuery<DeviceGroup[]>({
    queryKey: ["device-groups"],
    queryFn: deviceGroupsApi.list,
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => deviceGroupsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["device-groups"] }),
  });

  return (
    <>
      <div className="flex justify-between items-center mb-6">
        <p className="text-sm text-gray-500">Agrupe dispositivos por site ou função para operações recorrentes em lote.</p>
        {canWrite && (
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 transition-colors">
            <Plus size={16} /> Novo grupo
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-gray-400"><Loader2 size={16} className="animate-spin" /> Carregando grupos...</div>
      ) : groups.length === 0 ? (
        <EmptyState title="Nenhum grupo criado"
          description="Crie grupos para organizar dispositivos por site ou função e aplicar operações em lote com facilidade."
          action={canWrite ? (
            <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700">Criar primeiro grupo</button>
          ) : undefined}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {groups.map((group) => (
            <GroupCard key={group.id} group={group} onEdit={(g) => setEditGroup(g as DeviceGroup)}
              onDelete={(id) => setDeleteId(id)} canWrite={canWrite} />
          ))}
        </div>
      )}

      <GroupModal isOpen={showCreate} onClose={() => setShowCreate(false)} />
      {editGroup && <EditGroupWrapper groupId={editGroup.id} onClose={() => setEditGroup(null)} />}
      <ConfirmModal isOpen={!!deleteId} title="Remover grupo"
        description="Tem certeza que deseja remover este grupo? Os dispositivos não serão afetados."
        danger onConfirm={() => { if (deleteId) { deleteMut.mutate(deleteId); setDeleteId(null); } }}
        onCancel={() => setDeleteId(null)} confirmLabel="Remover" />
    </>
  );
}

function TemplatesTab() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.role === "admin";
  const qc = useQueryClient();
  const [searchParams] = useSearchParams();
  const editId = searchParams.get("edit");

  const [search, setSearch] = useState("");
  const [vendorFilter, setVendorFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [selected, setSelected] = useState<RuleTemplate | null>(null);
  const [editContext, setEditContext] = useState<{
    initialParams: Record<string, string>; initialDeviceId: string; parentOperationId: string;
  } | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const { data: templates = [], isLoading } = useQuery({
    queryKey: ["templates", vendorFilter, categoryFilter],
    queryFn: () => templatesApi.list({ vendor: vendorFilter || undefined, category: categoryFilter || undefined }),
  });
  const { data: editOp } = useQuery({
    queryKey: ["operation", editId],
    queryFn: () => operationsApi.get(editId!),
    enabled: !!editId,
    staleTime: Infinity,
  });

  useEffect(() => {
    if (!editOp || templates.length === 0) return;
    const slug = editOp.action_plan?.template_slug as string | undefined;
    if (!slug) return;
    const tpl = templates.find((t) => t.slug === slug);
    if (!tpl) return;
    setEditContext({
      initialParams: (editOp.action_plan?.template_params as Record<string, string>) ?? {},
      initialDeviceId: editOp.device_id,
      parentOperationId: editOp.id,
    });
    setSelected(tpl);
  }, [editOp?.id, templates.length]);

  const deleteMutation = useMutation({
    mutationFn: (slug: string) => templatesApi.delete(slug),
    onSuccess: () => { toast.success("Template removido."); qc.invalidateQueries({ queryKey: ["templates"] }); },
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
    <>
      {selected && (
        <TemplateModal template={selected} onClose={() => { setSelected(null); setEditContext(null); }}
          initialParams={editContext?.initialParams} initialDeviceId={editContext?.initialDeviceId}
          parentOperationId={editContext?.parentOperationId} />
      )}
      {showCreate && <CreateTemplateModal onClose={() => setShowCreate(false)} />}

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar templates..."
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
            <Plus size={15} /> Novo Template
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

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((t) => (
          <div key={t.slug} className="bg-white border border-gray-200 rounded-xl p-5 hover:border-brand-300 hover:shadow-sm transition-all group flex flex-col gap-3">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <Terminal size={16} className="text-brand-600 shrink-0" />
                <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">{t.category}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${t.is_builtin ? "bg-blue-50 text-blue-600" : "bg-purple-50 text-purple-600"}`}>
                  {t.is_builtin ? "Embutido" : "Custom"}
                </span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 font-medium">{VENDOR_LABELS[t.vendor] ?? t.vendor}</span>
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
                <ChevronRight size={13} /> Usar template
              </button>
              {isAdmin && !t.is_builtin && (
                <button onClick={() => { if (confirm(`Remover "${t.name}"?`)) deleteMutation.mutate(t.slug); }}
                  className="px-3 py-2 text-red-500 border border-red-200 rounded-lg hover:bg-red-50 text-xs">
                  <Trash2 size={13} />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function TenantVarsTab() {
  const qc = useQueryClient();
  const [modal, setModal] = useState<{ open: boolean; editing?: TenantVariable }>({ open: false });
  const { data: vars = [], isLoading } = useQuery({ queryKey: ["tenant-variables"], queryFn: variablesApi.listTenant });
  const createMut = useMutation({
    mutationFn: (d: VariableFormData) => variablesApi.createTenant({ name: d.name, value: d.value, variable_type: d.variable_type, description: d.description || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["tenant-variables"] }); setModal({ open: false }); toast.success("Variável criada"); },
    onError: () => toast.error("Erro ao criar variável. Verifique se o nome já existe."),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, d }: { id: string; d: VariableFormData }) => variablesApi.updateTenant(id, { value: d.value, variable_type: d.variable_type, description: d.description || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["tenant-variables"] }); setModal({ open: false }); toast.success("Variável atualizada"); },
    onError: () => toast.error("Erro ao atualizar variável"),
  });
  const deleteMut = useMutation({
    mutationFn: variablesApi.deleteTenant,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["tenant-variables"] }); toast.success("Variável removida"); },
    onError: () => toast.error("Erro ao remover variável"),
  });
  const handleSave = (d: VariableFormData) => { if (modal.editing) updateMut.mutate({ id: modal.editing.id, d }); else createMut.mutate(d); };
  const isBusy = createMut.isPending || updateMut.isPending;
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">Valem para todos os dispositivos. Podem ser sobrescritas por variável específica do device.</p>
        <button onClick={() => setModal({ open: true })} className="flex items-center gap-2 px-3 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm rounded-lg font-medium">
          <Plus size={14} /> Nova variável global
        </button>
      </div>
      {isLoading ? <p className="text-sm text-gray-400 py-8 text-center">Carregando...</p>
        : vars.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <Globe size={32} className="mx-auto mb-2 opacity-30" />
            <p className="text-sm">Nenhuma variável global cadastrada.</p>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
            {vars.map((v) => (
              <VarRow key={v.id} name={v.name} value={v.value} type={v.variable_type} description={v.description}
                onEdit={() => setModal({ open: true, editing: v })}
                onDelete={() => { if (confirm(`Remover variável {{${v.name}}}?`)) deleteMut.mutate(v.id); }} />
            ))}
          </div>
        )}
      {modal.open && (
        <VarModal title={modal.editing ? "Editar variável global" : "Nova variável global"}
          initial={modal.editing ? { name: modal.editing.name, value: modal.editing.value, variable_type: modal.editing.variable_type, description: modal.editing.description ?? "" } : EMPTY_FORM}
          nameReadOnly={!!modal.editing} onSave={handleSave} onClose={() => setModal({ open: false })} isLoading={isBusy} />
      )}
    </div>
  );
}

function DeviceVarsTab() {
  const qc = useQueryClient();
  const [selectedDevice, setSelectedDevice] = useState<string>("");
  const [modal, setModal] = useState<{ open: boolean; editing?: DeviceVariable }>({ open: false });
  const { data: devices = [] } = useQuery({ queryKey: ["devices"], queryFn: devicesApi.list });
  const { data: vars = [], isLoading } = useQuery({
    queryKey: ["device-variables", selectedDevice],
    queryFn: () => variablesApi.listDevice(selectedDevice),
    enabled: !!selectedDevice,
  });
  const createMut = useMutation({
    mutationFn: (d: VariableFormData) => variablesApi.createDevice(selectedDevice, { name: d.name, value: d.value, variable_type: d.variable_type, description: d.description || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["device-variables", selectedDevice] }); setModal({ open: false }); toast.success("Variável criada"); },
    onError: () => toast.error("Erro ao criar variável. Verifique se o nome já existe neste device."),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, d }: { id: string; d: VariableFormData }) => variablesApi.updateDevice(selectedDevice, id, { value: d.value, variable_type: d.variable_type, description: d.description || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["device-variables", selectedDevice] }); setModal({ open: false }); toast.success("Variável atualizada"); },
    onError: () => toast.error("Erro ao atualizar variável"),
  });
  const deleteMut = useMutation({
    mutationFn: (varId: string) => variablesApi.deleteDevice(selectedDevice, varId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["device-variables", selectedDevice] }); toast.success("Variável removida"); },
    onError: () => toast.error("Erro ao remover variável"),
  });
  const handleSave = (d: VariableFormData) => { if (modal.editing) updateMut.mutate({ id: modal.editing.id, d }); else createMut.mutate(d); };
  const isBusy = createMut.isPending || updateMut.isPending;
  const selectedDev = devices.find((d) => d.id === selectedDevice);

  return (
    <div>
      <div className="mb-5">
        <label className="block text-xs font-medium text-gray-700 mb-1">Selecione o dispositivo</label>
        <div className="relative max-w-sm">
          <select value={selectedDevice} onChange={(e) => setSelectedDevice(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-brand-500 pr-8">
            <option value="">-- escolha um device --</option>
            {devices.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.vendor})</option>)}
          </select>
          <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
        </div>
      </div>
      {!selectedDevice ? (
        <div className="text-center py-12 text-gray-400">
          <Server size={32} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">Selecione um dispositivo para gerenciar suas variáveis.</p>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-gray-500">
              Variáveis de <span className="font-medium text-gray-700">{selectedDev?.name}</span>. Sobrescrevem variáveis globais de mesmo nome.
            </p>
            <button onClick={() => setModal({ open: true })} className="flex items-center gap-2 px-3 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm rounded-lg font-medium">
              <Plus size={14} /> Nova variável
            </button>
          </div>
          {isLoading ? <p className="text-sm text-gray-400 py-8 text-center">Carregando...</p>
            : vars.length === 0 ? (
              <div className="text-center py-12 text-gray-400">
                <Tag size={32} className="mx-auto mb-2 opacity-30" />
                <p className="text-sm">Nenhuma variável específica cadastrada para este device.</p>
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
                {vars.map((v) => (
                  <VarRow key={v.id} name={v.name} value={v.value} type={v.variable_type} description={v.description}
                    badge={v.overrides_tenant ? (
                      <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">sobrescreve global</span>
                    ) : undefined}
                    onEdit={() => setModal({ open: true, editing: v })}
                    onDelete={() => { if (confirm(`Remover variável {{${v.name}}} deste device?`)) deleteMut.mutate(v.id); }} />
                ))}
              </div>
            )}
        </>
      )}
      {modal.open && (
        <VarModal title={modal.editing ? "Editar variável do device" : "Nova variável do device"}
          initial={modal.editing ? { name: modal.editing.name, value: modal.editing.value, variable_type: modal.editing.variable_type, description: modal.editing.description ?? "" } : EMPTY_FORM}
          nameReadOnly={!!modal.editing} onSave={handleSave} onClose={() => setModal({ open: false })} isLoading={isBusy} />
      )}
    </div>
  );
}

function PreviewTab() {
  const [text, setText] = useState("");
  const [deviceIds, setDeviceIds] = useState<string[]>([]);
  const [result, setResult] = useState<import("../types/variable").BulkJobPreviewResponse | null>(null);
  const { data: devices = [] } = useQuery({ queryKey: ["devices"], queryFn: devicesApi.list });
  const previewMut = useMutation({
    mutationFn: variablesApi.preview,
    onSuccess: (data) => setResult(data),
    onError: () => toast.error("Erro ao gerar preview"),
  });
  const toggleDevice = (id: string) =>
    setDeviceIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  return (
    <div className="space-y-5">
      <p className="text-sm text-gray-500">Simule como as variáveis serão resolvidas para cada device <strong>sem criar o job</strong>.</p>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Texto com variáveis</label>
        <textarea rows={3} value={text} onChange={(e) => { setText(e.target.value); setResult(null); }}
          placeholder={`Crie uma regra liberando {{rede_local}} para {{dns}} na porta 53`}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono" />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-2">Dispositivos</label>
        <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto">
          {devices.map((d) => (
            <label key={d.id} className={`flex items-center gap-2 px-3 py-2 border rounded-lg cursor-pointer text-sm transition-colors ${deviceIds.includes(d.id) ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-200 hover:border-gray-300"}`}>
              <input type="checkbox" checked={deviceIds.includes(d.id)} onChange={() => toggleDevice(d.id)} className="accent-brand-600" />
              <span className="truncate">{d.name}</span>
              <span className="text-xs text-gray-400 ml-auto shrink-0">{d.vendor}</span>
            </label>
          ))}
        </div>
      </div>
      <button onClick={() => previewMut.mutate({ device_ids: deviceIds, natural_language_input: text })}
        disabled={text.trim().length === 0 || deviceIds.length === 0 || previewMut.isPending}
        className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm rounded-lg disabled:opacity-50 font-medium">
        {previewMut.isPending ? <span className="animate-spin border-2 border-white border-t-transparent rounded-full w-3 h-3" /> : null}
        Simular resolução
      </button>
      {result && (
        <div className="space-y-3">
          <div className={`flex items-center gap-2 text-sm font-medium px-3 py-2 rounded-lg ${result.all_ready ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
            {result.all_ready ? <Check size={15} /> : <AlertTriangle size={15} />}
            {result.all_ready ? "Todos os devices prontos — nenhuma variável faltando." : "Atenção: alguns devices têm variáveis não definidas."}
          </div>
          {result.devices.map((dev) => (
            <div key={dev.device_id} className={`bg-white rounded-xl border p-4 ${dev.ready ? "border-gray-200" : "border-red-200"}`}>
              <div className="flex items-center gap-2 mb-3">
                <Server size={14} className="text-gray-400" />
                <span className="text-sm font-semibold text-gray-800">{dev.device_name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ml-auto ${dev.ready ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                  {dev.ready ? "Pronto" : "Faltando variáveis"}
                </span>
              </div>
              {dev.unresolved_variables.length > 0 && (
                <div className="mb-3 flex flex-wrap gap-1">
                  {dev.unresolved_variables.map((v) => (
                    <span key={v} className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded font-mono">{`{{${v}}}`} não definida</span>
                  ))}
                </div>
              )}
              <div className="space-y-1 text-xs">
                <p className="text-gray-400 font-medium uppercase tracking-wide">Original</p>
                <p className="font-mono text-gray-600 bg-gray-50 rounded px-2 py-1.5">{dev.original_input}</p>
                <p className="text-gray-400 font-medium uppercase tracking-wide mt-2">Resolvido</p>
                <p className="font-mono text-gray-800 bg-brand-50 rounded px-2 py-1.5">{dev.resolved_input}</p>
              </div>
              {dev.variables_resolved.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-100">
                  <p className="text-xs text-gray-400 font-medium uppercase tracking-wide mb-2">Variáveis utilizadas</p>
                  <div className="space-y-1">
                    {dev.variables_resolved.map((rv) => (
                      <div key={rv.name} className="flex items-center gap-2 text-xs">
                        <code className="font-mono text-gray-700">{`{{${rv.name}}}`}</code>
                        <span className="text-gray-400">→</span>
                        <code className="font-mono text-brand-700">{rv.value}</code>
                        <span className={`ml-auto px-1.5 py-0.5 rounded text-xs ${rv.source === "device" ? "bg-purple-100 text-purple-700" : "bg-gray-100 text-gray-600"}`}>
                          {rv.source === "device" ? "device" : "global"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

type VarInnerTab = "global" | "device" | "preview";

function VariaveisTab() {
  const [innerTab, setInnerTab] = useState<VarInnerTab>("global");
  const innerTabs: { id: VarInnerTab; label: string; icon: React.ElementType }[] = [
    { id: "global",  label: "Variáveis Globais", icon: Globe },
    { id: "device",  label: "Por Dispositivo",   icon: Server },
    { id: "preview", label: "Preview / Dry-run", icon: Check },
  ];
  return (
    <div className="max-w-4xl">
      <div className="bg-brand-50 border border-brand-200 rounded-xl p-4 mb-6 text-sm text-brand-700">
        <p className="font-semibold mb-1">Como usar variáveis</p>
        <p>
          Use <code className="bg-white px-1 rounded border border-brand-200">{`{{nome_variavel}}`}</code> em qualquer mensagem para o agente ou operação em lote.
          O sistema substitui automaticamente pelo valor correto de cada device antes de enviar ao AI.
        </p>
      </div>
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 mb-6">
        {innerTabs.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setInnerTab(id)}
            className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
              innerTab === id ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
            }`}>
            <Icon size={15} />{label}
          </button>
        ))}
      </div>
      {innerTab === "global"  && <TenantVarsTab />}
      {innerTab === "device"  && <DeviceVarsTab />}
      {innerTab === "preview" && <PreviewTab />}
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

const OUTER_TABS: { id: OuterTab; label: string }[] = [
  { id: "dispositivos", label: "Dispositivos" },
  { id: "grupos",       label: "Grupos" },
  { id: "templates",    label: "Templates" },
  { id: "variaveis",    label: "Variáveis" },
];

export function Devices() {
  const [searchParams] = useSearchParams();
  const initialTab: OuterTab = searchParams.has("edit") ? "templates" : "dispositivos";
  const [tab, setTab] = useState<OuterTab>(initialTab);

  return (
    <PageWrapper title="Dispositivos">
      <div className="flex gap-1 border-b border-gray-200 mb-6 -mt-2">
        {OUTER_TABS.map(({ id, label }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === id
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            }`}>
            {label}
          </button>
        ))}
      </div>
      {tab === "dispositivos" && <DevicesTab />}
      {tab === "grupos"       && <GruposTab />}
      {tab === "templates"    && <TemplatesTab />}
      {tab === "variaveis"    && <VariaveisTab />}
    </PageWrapper>
  );
}
