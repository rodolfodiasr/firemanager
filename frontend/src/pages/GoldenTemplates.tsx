import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Copy,
  GitBranch,
  Loader2,
  Pencil,
  Play,
  Plus,
  RotateCcw,
  Save,
  Shield,
  Trash2,
  X,
  XCircle,
  AlertTriangle,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { goldenTemplateApi } from "../api/goldenTemplate";
import { devicesApi } from "../api/devices";
import type {
  DivergenceItem,
  DivergenceResponse,
  GoldenTemplateRead,
  GoldenTemplateSummary,
  TemplateVariable,
} from "../types/goldenTemplate";
import type { Device } from "../types/device";

// ── Constants ─────────────────────────────────────────────────────────────────

const VENDOR_LABEL: Record<string, string> = {
  any: "Qualquer",
  fortinet: "Fortinet",
  sonicwall: "SonicWall",
  sophos: "Sophos",
  pfsense: "pfSense",
  opnsense: "OPNsense",
  mikrotik: "MikroTik",
  endian: "Endian",
  cisco_ios: "Cisco IOS",
  cisco_nxos: "Cisco NX-OS",
  juniper: "Juniper",
  aruba: "Aruba",
  dell: "Dell",
  dell_n: "Dell N",
  hp_comware: "HP Comware",
  ubiquiti: "Ubiquiti",
  edgeswitch: "EdgeSwitch",
};

const CATEGORY_LABEL: Record<string, string> = {
  filial: "Filial",
  matriz: "Matriz",
  switch_acesso: "Switch Acesso",
  dmz: "DMZ",
  custom: "Personalizado",
};

const VAR_TYPE_LABEL: Record<string, string> = {
  ip: "IP",
  cidr: "CIDR",
  string: "Texto",
  integer: "Número",
  hostname: "Hostname",
};

function vendorBadge(vendor: string) {
  const v = VENDOR_LABEL[vendor] ?? vendor;
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
      {v}
    </span>
  );
}

function categoryBadge(cat: string) {
  const c = CATEGORY_LABEL[cat] ?? cat;
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
      {c}
    </span>
  );
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR");
}

// ── Variable editor row ───────────────────────────────────────────────────────

function VariableRow({
  variable,
  onChange,
  onRemove,
  readonly,
}: {
  variable: TemplateVariable;
  onChange: (v: TemplateVariable) => void;
  onRemove: () => void;
  readonly?: boolean;
}) {
  return (
    <div className="grid grid-cols-12 gap-2 items-center py-1">
      <input
        className="col-span-2 border rounded px-2 py-1 text-xs"
        placeholder="KEY"
        value={variable.key}
        disabled={readonly}
        onChange={(e) => onChange({ ...variable, key: e.target.value.toUpperCase().replace(/\s/g, "_") })}
      />
      <select
        className="col-span-2 border rounded px-2 py-1 text-xs"
        value={variable.type}
        disabled={readonly}
        onChange={(e) => onChange({ ...variable, type: e.target.value as TemplateVariable["type"] })}
      >
        {Object.entries(VAR_TYPE_LABEL).map(([k, l]) => (
          <option key={k} value={k}>{l}</option>
        ))}
      </select>
      <input
        className="col-span-3 border rounded px-2 py-1 text-xs"
        placeholder="Label"
        value={variable.label}
        disabled={readonly}
        onChange={(e) => onChange({ ...variable, label: e.target.value })}
      />
      <input
        className="col-span-2 border rounded px-2 py-1 text-xs"
        placeholder="Padrão"
        value={variable.default ?? ""}
        disabled={readonly}
        onChange={(e) => onChange({ ...variable, default: e.target.value || undefined })}
      />
      <label className="col-span-2 flex items-center gap-1 text-xs">
        <input
          type="checkbox"
          checked={variable.required}
          disabled={readonly}
          onChange={(e) => onChange({ ...variable, required: e.target.checked })}
        />
        Obrig.
      </label>
      {!readonly && (
        <button onClick={onRemove} className="col-span-1 text-red-400 hover:text-red-600">
          <X size={14} />
        </button>
      )}
    </div>
  );
}

// ── Template Editor Modal ─────────────────────────────────────────────────────

function TemplateEditorModal({
  initial,
  onClose,
  onSave,
}: {
  initial?: GoldenTemplateRead;
  onClose: () => void;
  onSave: (data: {
    name: string;
    description: string;
    vendor: string;
    category: string;
    variables: TemplateVariable[];
    content: string;
    change_note: string;
  }) => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [vendor, setVendor] = useState(initial?.vendor ?? "any");
  const [category, setCategory] = useState(initial?.category ?? "custom");
  const [variables, setVariables] = useState<TemplateVariable[]>(
    (initial?.variables as TemplateVariable[]) ?? []
  );
  const [content, setContent] = useState(initial?.content ?? "");
  const [changeNote, setChangeNote] = useState("");
  const [tab, setTab] = useState<"info" | "vars" | "content">("info");

  const addVar = () =>
    setVariables((v) => [
      ...v,
      { key: "", type: "string", label: "", required: true },
    ]);

  const updateVar = (i: number, v: TemplateVariable) =>
    setVariables((vars) => vars.map((x, idx) => (idx === i ? v : x)));

  const removeVar = (i: number) =>
    setVariables((vars) => vars.filter((_, idx) => idx !== i));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">
            {initial ? "Editar Template" : "Novo Template"}
          </h2>
          <button onClick={onClose}><X size={20} /></button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-6 pt-3 border-b">
          {(["info", "vars", "content"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors ${
                tab === t ? "border-brand-600 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t === "info" ? "Informações" : t === "vars" ? `Variáveis (${variables.length})` : "Conteúdo"}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {tab === "info" && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
                <input
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ex: Filial Padrão Cisco"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Descrição</label>
                <textarea
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Vendor</label>
                  <select
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={vendor}
                    onChange={(e) => setVendor(e.target.value)}
                  >
                    {Object.entries(VENDOR_LABEL).map(([k, l]) => (
                      <option key={k} value={k}>{l}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Categoria</label>
                  <select
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                  >
                    {Object.entries(CATEGORY_LABEL).map(([k, l]) => (
                      <option key={k} value={k}>{l}</option>
                    ))}
                  </select>
                </div>
              </div>
              {initial && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Nota da alteração
                  </label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={changeNote}
                    onChange={(e) => setChangeNote(e.target.value)}
                    placeholder="Ex: Adicionado NTP redundante"
                  />
                </div>
              )}
            </div>
          )}

          {tab === "vars" && (
            <div>
              <div className="grid grid-cols-12 gap-2 text-xs font-medium text-gray-500 mb-2 px-1">
                <span className="col-span-2">Chave</span>
                <span className="col-span-2">Tipo</span>
                <span className="col-span-3">Label</span>
                <span className="col-span-2">Padrão</span>
                <span className="col-span-2">Req.</span>
                <span className="col-span-1"></span>
              </div>
              {variables.map((v, i) => (
                <VariableRow
                  key={i}
                  variable={v}
                  onChange={(nv) => updateVar(i, nv)}
                  onRemove={() => removeVar(i)}
                />
              ))}
              <button
                onClick={addVar}
                className="mt-3 flex items-center gap-1 text-sm text-brand-600 hover:text-brand-700"
              >
                <Plus size={14} /> Adicionar variável
              </button>
              <p className="mt-3 text-xs text-gray-500">
                Use <code className="bg-gray-100 px-1 rounded">{"{CHAVE}"}</code> no conteúdo para referenciar cada variável.
              </p>
            </div>
          )}

          {tab === "content" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Comandos CLI (use {"{VARIAVEL}"} como placeholder)
              </label>
              <textarea
                className="w-full border rounded-lg px-3 py-2 text-sm font-mono text-xs bg-gray-50"
                rows={18}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="hostname {BRANCH_NAME}&#10;&#10;interface Vlan{VLAN_MGMT}&#10; ip address {MGMT_IP}&#10; no shutdown"
                spellCheck={false}
              />
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200">
            Cancelar
          </button>
          <button
            onClick={() => onSave({ name, description, vendor, category, variables, content, change_note: changeNote })}
            disabled={!name || !content}
            className="px-4 py-2 text-sm text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Save size={14} /> Salvar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Apply Wizard Modal ────────────────────────────────────────────────────────

function ApplyWizard({
  template,
  devices,
  onClose,
}: {
  template: GoldenTemplateSummary;
  devices: Device[];
  onClose: () => void;
}) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [deviceId, setDeviceId] = useState("");
  const [varValues, setVarValues] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState("");
  const [editingPreview, setEditingPreview] = useState(false);
  const [previewDraft, setPreviewDraft] = useState("");
  const [applyResult, setApplyResult] = useState<{ status: string; message: string; output?: string } | null>(null);

  // Full template (with variables list) loaded on demand
  const { data: fullTpl } = useQuery({
    queryKey: ["golden-template", template.id],
    queryFn: () => goldenTemplateApi.get(template.id),
  });

  // Prefill variables when device selected
  const prefillMut = useMutation({
    mutationFn: () => goldenTemplateApi.prefill(template.id, deviceId),
    onSuccess: (data) => {
      setVarValues((prev) => ({ ...prev, ...data.variable_values }));
    },
  });

  const renderMut = useMutation({
    mutationFn: () => goldenTemplateApi.render(template.id, varValues),
    onSuccess: (data) => {
      setPreview(data.content);
      setPreviewDraft(data.content);
      setStep(3);
    },
    onError: () => toast.error("Erro ao renderizar template"),
  });

  const applyMut = useMutation({
    mutationFn: () =>
      goldenTemplateApi.apply(template.id, deviceId, varValues),
    onSuccess: (data) => setApplyResult(data),
    onError: () => toast.error("Erro ao aplicar template"),
  });

  const variables = (fullTpl?.variables ?? []) as TemplateVariable[];

  const handleDeviceSelect = (id: string) => {
    setDeviceId(id);
    if (id) {
      setTimeout(() => prefillMut.mutate(), 0);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="text-lg font-semibold">Aplicar Template</h2>
            <p className="text-sm text-gray-500">{template.name}</p>
          </div>
          <button onClick={onClose}><X size={20} /></button>
        </div>

        {/* Step indicators */}
        <div className="flex items-center gap-2 px-6 py-3 border-b bg-gray-50">
          {([1, 2, 3] as const).map((s) => (
            <div key={s} className="flex items-center gap-2">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                step > s ? "bg-green-500 text-white" : step === s ? "bg-brand-600 text-white" : "bg-gray-200 text-gray-500"
              }`}>
                {step > s ? <CheckCircle2 size={14} /> : s}
              </div>
              <span className={`text-xs ${step === s ? "font-medium text-gray-800" : "text-gray-400"}`}>
                {s === 1 ? "Dispositivo" : s === 2 ? "Variáveis" : "Confirmar"}
              </span>
              {s < 3 && <ChevronRight size={14} className="text-gray-300" />}
            </div>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {/* Step 1 - Select device */}
          {step === 1 && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">Selecione o dispositivo de destino para aplicar o template.</p>
              <select
                value={deviceId}
                onChange={(e) => handleDeviceSelect(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              >
                <option value="">Selecione um dispositivo…</option>
                {devices.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} — {VENDOR_LABEL[d.vendor] ?? d.vendor} ({d.host})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Step 2 - Fill variables */}
          {step === 2 && (
            <div className="space-y-3">
              <p className="text-sm text-gray-600">
                Preencha as variáveis do template. Valores já preenchidos foram herdados das variáveis do dispositivo/tenant.
              </p>
              {variables.length === 0 && (
                <p className="text-sm text-gray-500 italic">Este template não possui variáveis.</p>
              )}
              {variables.map((v) => (
                <div key={v.key}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {v.label}
                    <code className="ml-2 text-xs text-gray-400">{`{${v.key}}`}</code>
                    {v.required && <span className="ml-1 text-red-500">*</span>}
                  </label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    placeholder={v.hint ?? v.default ?? ""}
                    value={varValues[v.key] ?? v.default ?? ""}
                    onChange={(e) => setVarValues((prev) => ({ ...prev, [v.key]: e.target.value }))}
                  />
                  {v.hint && <p className="text-xs text-gray-400 mt-0.5">{v.hint}</p>}
                </div>
              ))}
            </div>
          )}

          {/* Step 3 - Preview & Apply */}
          {step === 3 && !applyResult && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">Preview dos comandos</span>
                {!editingPreview ? (
                  <button
                    onClick={() => setEditingPreview(true)}
                    className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-700"
                  >
                    <Pencil size={12} /> Editar
                  </button>
                ) : (
                  <button
                    onClick={() => { setPreview(previewDraft); setEditingPreview(false); }}
                    className="flex items-center gap-1 text-xs text-green-600 hover:text-green-700"
                  >
                    <Save size={12} /> Salvar edição
                  </button>
                )}
              </div>
              {editingPreview ? (
                <textarea
                  className="w-full h-64 border rounded-lg px-3 py-2 text-xs font-mono bg-gray-50"
                  value={previewDraft}
                  onChange={(e) => setPreviewDraft(e.target.value)}
                  spellCheck={false}
                />
              ) : (
                <pre className="w-full h-64 overflow-auto border rounded-lg px-3 py-2 text-xs font-mono bg-gray-50 whitespace-pre-wrap">
                  {preview}
                </pre>
              )}
            </div>
          )}

          {/* Apply result */}
          {applyResult && (
            <div className={`rounded-lg p-4 ${
              applyResult.status === "applied" ? "bg-green-50 border border-green-200" :
              applyResult.status === "manual"  ? "bg-amber-50 border border-amber-200" :
              "bg-red-50 border border-red-200"
            }`}>
              <div className="flex items-center gap-2 mb-2">
                {applyResult.status === "applied" ? <CheckCircle2 className="text-green-600" size={18} /> :
                 applyResult.status === "manual"  ? <AlertTriangle className="text-amber-600" size={18} /> :
                 <XCircle className="text-red-600" size={18} />}
                <span className="font-medium text-sm">{applyResult.message}</span>
              </div>
              {applyResult.output && (
                <pre className="text-xs font-mono bg-white/70 rounded p-2 overflow-auto max-h-40 mt-2">
                  {applyResult.output}
                </pre>
              )}
              {applyResult.commands && (
                <pre className="text-xs font-mono bg-white/70 rounded p-2 overflow-auto max-h-40 mt-2 whitespace-pre-wrap">
                  {applyResult.commands}
                </pre>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-between px-6 py-4 border-t">
          <button
            onClick={() => step > 1 ? setStep((s) => (s - 1) as 1 | 2 | 3) : onClose()}
            className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
          >
            {step === 1 ? "Cancelar" : "Voltar"}
          </button>

          {!applyResult && (
            <button
              disabled={
                (step === 1 && !deviceId) ||
                (step === 2 && variables.filter((v) => v.required).some((v) => !(varValues[v.key] ?? v.default))) ||
                renderMut.isPending ||
                applyMut.isPending
              }
              onClick={() => {
                if (step === 1) setStep(2);
                else if (step === 2) renderMut.mutate();
                else applyMut.mutate();
              }}
              className="px-4 py-2 text-sm text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2"
            >
              {(renderMut.isPending || applyMut.isPending) && <Loader2 size={14} className="animate-spin" />}
              {step === 3 ? <><Play size={14} /> Aplicar</> : "Próximo"}
            </button>
          )}

          {applyResult && (
            <button onClick={onClose} className="px-4 py-2 text-sm text-white bg-brand-600 rounded-lg hover:bg-brand-700">
              Fechar
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Divergence Modal ──────────────────────────────────────────────────────────

function DivergenceModal({
  template,
  devices,
  onClose,
}: {
  template: GoldenTemplateSummary;
  devices: Device[];
  onClose: () => void;
}) {
  const [deviceId, setDeviceId] = useState("");
  const [varValues, setVarValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<DivergenceResponse | null>(null);
  const [groupBy, setGroupBy] = useState<"section" | "status">("section");

  const { data: fullTpl } = useQuery({
    queryKey: ["golden-template", template.id],
    queryFn: () => goldenTemplateApi.get(template.id),
  });

  const variables = (fullTpl?.variables ?? []) as TemplateVariable[];

  const prefillMut = useMutation({
    mutationFn: () => goldenTemplateApi.prefill(template.id, deviceId),
    onSuccess: (data) => setVarValues((prev) => ({ ...prev, ...data.variable_values })),
  });

  const analyzeMut = useMutation({
    mutationFn: () => goldenTemplateApi.divergence(template.id, deviceId, varValues),
    onSuccess: setResult,
    onError: () => toast.error("Erro ao analisar divergência"),
  });

  const grouped = result
    ? result.items.reduce<Record<string, DivergenceItem[]>>((acc, item) => {
        const key = groupBy === "section" ? item.section : item.status;
        (acc[key] = acc[key] ?? []).push(item);
        return acc;
      }, {})
    : {};

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="text-lg font-semibold">Relatório de Divergência</h2>
            <p className="text-sm text-gray-500">{template.name}</p>
          </div>
          <button onClick={onClose}><X size={20} /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {!result ? (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Dispositivo</label>
                <select
                  value={deviceId}
                  onChange={(e) => {
                    setDeviceId(e.target.value);
                    if (e.target.value) setTimeout(() => prefillMut.mutate(), 0);
                  }}
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                >
                  <option value="">Selecione…</option>
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} — {VENDOR_LABEL[d.vendor] ?? d.vendor} ({d.host})
                    </option>
                  ))}
                </select>
              </div>

              {variables.map((v) => (
                <div key={v.key}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {v.label} <code className="text-xs text-gray-400">{`{${v.key}}`}</code>
                    {v.required && <span className="text-red-500 ml-1">*</span>}
                  </label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    placeholder={v.hint ?? v.default ?? ""}
                    value={varValues[v.key] ?? v.default ?? ""}
                    onChange={(e) => setVarValues((p) => ({ ...p, [v.key]: e.target.value }))}
                  />
                </div>
              ))}

              <button
                onClick={() => analyzeMut.mutate()}
                disabled={!deviceId || analyzeMut.isPending}
                className="w-full flex items-center justify-center gap-2 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 text-sm"
              >
                {analyzeMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Shield size={14} />}
                {analyzeMut.isPending ? "Conectando ao dispositivo…" : "Analisar Divergência"}
              </button>
            </div>
          ) : (
            <div>
              {/* Summary cards */}
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-red-600">{result.summary.missing ?? 0}</p>
                  <p className="text-xs text-red-700">Ausentes no device</p>
                </div>
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-amber-600">{result.summary.extra ?? 0}</p>
                  <p className="text-xs text-amber-700">Extras no device</p>
                </div>
                <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-green-600">
                    {result.supported && !result.message
                      ? result.items.length === 0 ? "OK" : "⚠"
                      : "—"}
                  </p>
                  <p className="text-xs text-green-700">Status geral</p>
                </div>
              </div>

              {result.message && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-sm text-amber-800">
                  <AlertTriangle size={14} className="inline mr-1" />
                  {result.message}
                </div>
              )}

              {result.items.length === 0 && result.supported && !result.message && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center text-green-700">
                  <CheckCircle2 size={32} className="mx-auto mb-2" />
                  <p className="font-medium">Dispositivo em conformidade com o template!</p>
                </div>
              )}

              {result.items.length > 0 && (
                <>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium text-gray-700">
                      {result.items.length} diferença{result.items.length !== 1 ? "s" : ""} encontrada{result.items.length !== 1 ? "s" : ""}
                    </span>
                    <select
                      value={groupBy}
                      onChange={(e) => setGroupBy(e.target.value as "section" | "status")}
                      className="text-xs border rounded px-2 py-1"
                    >
                      <option value="section">Agrupar por seção</option>
                      <option value="status">Agrupar por tipo</option>
                    </select>
                  </div>

                  {Object.entries(grouped).map(([group, items]) => (
                    <div key={group} className="mb-3">
                      <div className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1 px-1">
                        {groupBy === "status"
                          ? group === "missing" ? "⬇ Ausentes no dispositivo" : "⬆ Extras no dispositivo"
                          : group}
                      </div>
                      <div className="space-y-1">
                        {items.map((item, i) => (
                          <div
                            key={i}
                            className={`flex items-start gap-2 px-3 py-1.5 rounded text-xs font-mono ${
                              item.status === "missing"
                                ? "bg-red-50 text-red-800 border border-red-100"
                                : "bg-amber-50 text-amber-800 border border-amber-100"
                            }`}
                          >
                            <span>{item.status === "missing" ? "−" : "+"}</span>
                            <span>{item.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-between px-6 py-4 border-t">
          {result && (
            <button
              onClick={() => setResult(null)}
              className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            >
              Nova análise
            </button>
          )}
          <button onClick={onClose} className="ml-auto px-4 py-2 text-sm text-white bg-brand-600 rounded-lg hover:bg-brand-700">
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Version History Modal ─────────────────────────────────────────────────────

function VersionHistoryModal({
  template,
  onClose,
  onRestore,
}: {
  template: GoldenTemplateSummary;
  onClose: () => void;
  onRestore: (version: number) => void;
}) {
  const { data: versions = [], isLoading } = useQuery({
    queryKey: ["golden-template-versions", template.id],
    queryFn: () => goldenTemplateApi.versions(template.id),
    enabled: !template.is_system,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">Histórico de Versões</h2>
          <button onClick={onClose}><X size={20} /></button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {isLoading && <Loader2 className="animate-spin mx-auto" />}
          {template.is_system && (
            <p className="text-sm text-gray-500 text-center">Templates de sistema não possuem histórico.</p>
          )}
          {versions.map((v) => (
            <div key={v.id} className="flex items-center justify-between py-3 border-b last:border-0">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">v{v.version}</span>
                  {v.change_note && (
                    <span className="text-sm text-gray-600">{v.change_note}</span>
                  )}
                </div>
                <p className="text-xs text-gray-400">{fmtDate(v.created_at)}</p>
              </div>
              <button
                onClick={() => onRestore(v.version)}
                className="flex items-center gap-1 text-xs text-amber-600 hover:text-amber-700 border border-amber-300 rounded px-2 py-1"
              >
                <RotateCcw size={12} /> Restaurar
              </button>
            </div>
          ))}
        </div>
        <div className="flex justify-end px-6 py-4 border-t">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200">
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Template Card ─────────────────────────────────────────────────────────────

function TemplateCard({
  template,
  devices,
  onEdit,
  onDelete,
}: {
  template: GoldenTemplateSummary;
  devices: Device[];
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [showApply, setShowApply] = useState(false);
  const [showDivergence, setShowDivergence] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const qc = useQueryClient();

  const forkMut = useMutation({
    mutationFn: () => goldenTemplateApi.fork(template.id),
    onSuccess: () => {
      toast.success("Template duplicado com sucesso");
      qc.invalidateQueries({ queryKey: ["golden-templates"] });
    },
  });

  const restoreMut = useMutation({
    mutationFn: (version: number) => goldenTemplateApi.restoreVersion(template.id, version),
    onSuccess: () => {
      toast.success("Versão restaurada");
      qc.invalidateQueries({ queryKey: ["golden-templates"] });
      setShowHistory(false);
    },
  });

  return (
    <>
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              {template.is_system && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                  <BookOpen size={10} className="mr-1" /> Sistema
                </span>
              )}
              {vendorBadge(template.vendor)}
              {categoryBadge(template.category)}
            </div>
            <h3 className="font-semibold text-gray-900 text-sm leading-tight">{template.name}</h3>
            {template.description && (
              <p className="text-xs text-gray-500 mt-1 line-clamp-2">{template.description}</p>
            )}
          </div>
        </div>

        {/* Meta */}
        <div className="flex items-center gap-4 text-xs text-gray-400 mb-4">
          <span>{template.variable_count} variável{template.variable_count !== 1 ? "is" : ""}</span>
          <span>v{template.version}</span>
          {!template.is_system && <span>{fmtDate(template.updated_at)}</span>}
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setShowApply(true)}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-white bg-brand-600 rounded-lg hover:bg-brand-700"
          >
            <Play size={12} /> Aplicar
          </button>
          <button
            onClick={() => setShowDivergence(true)}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg hover:bg-amber-100"
          >
            <Shield size={12} /> Divergência
          </button>
          <button
            onClick={() => forkMut.mutate()}
            disabled={forkMut.isPending}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
          >
            <Copy size={12} /> Duplicar
          </button>
          {!template.is_system && (
            <>
              <button
                onClick={() => setShowHistory(true)}
                className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
              >
                <GitBranch size={12} /> Histórico
              </button>
              <button
                onClick={onEdit}
                className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
              >
                <Pencil size={12} /> Editar
              </button>
              <button
                onClick={onDelete}
                className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100"
              >
                <Trash2 size={12} /> Excluir
              </button>
            </>
          )}
        </div>
      </div>

      {showApply && (
        <ApplyWizard template={template} devices={devices} onClose={() => setShowApply(false)} />
      )}
      {showDivergence && (
        <DivergenceModal template={template} devices={devices} onClose={() => setShowDivergence(false)} />
      )}
      {showHistory && !template.is_system && (
        <VersionHistoryModal
          template={template}
          onClose={() => setShowHistory(false)}
          onRestore={(v) => restoreMut.mutate(v)}
        />
      )}
    </>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function GoldenTemplates() {
  const qc = useQueryClient();
  const [filterVendor, setFilterVendor] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [filterSearch, setFilterSearch] = useState("");
  const [showEditor, setShowEditor] = useState(false);
  const [editTarget, setEditTarget] = useState<GoldenTemplateRead | null>(null);

  const { data: templates = [], isLoading } = useQuery({
    queryKey: ["golden-templates"],
    queryFn: goldenTemplateApi.list,
  });

  const { data: devices = [] } = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.getAll,
  });

  const createMut = useMutation({
    mutationFn: (data: Parameters<typeof goldenTemplateApi.create>[0]) =>
      goldenTemplateApi.create(data),
    onSuccess: () => {
      toast.success("Template criado");
      qc.invalidateQueries({ queryKey: ["golden-templates"] });
      setShowEditor(false);
    },
    onError: () => toast.error("Erro ao criar template"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof goldenTemplateApi.update>[1] }) =>
      goldenTemplateApi.update(id, data),
    onSuccess: () => {
      toast.success("Template atualizado");
      qc.invalidateQueries({ queryKey: ["golden-templates"] });
      setShowEditor(false);
      setEditTarget(null);
    },
    onError: () => toast.error("Erro ao atualizar template"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => goldenTemplateApi.delete(id),
    onSuccess: () => {
      toast.success("Template excluído");
      qc.invalidateQueries({ queryKey: ["golden-templates"] });
    },
  });

  const handleSave = (data: {
    name: string;
    description: string;
    vendor: string;
    category: string;
    variables: TemplateVariable[];
    content: string;
    change_note: string;
  }) => {
    if (editTarget) {
      updateMut.mutate({ id: String(editTarget.id), data });
    } else {
      createMut.mutate(data);
    }
  };

  const filtered = templates.filter((t) => {
    if (filterVendor && t.vendor !== filterVendor) return false;
    if (filterCategory && t.category !== filterCategory) return false;
    if (filterSearch && !t.name.toLowerCase().includes(filterSearch.toLowerCase())) return false;
    return true;
  });

  const vendors = [...new Set(templates.map((t) => t.vendor))];
  const categories = [...new Set(templates.map((t) => t.category))];

  return (
    <PageWrapper title="Golden Config" subtitle="Biblioteca de templates e conformidade de configuração">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <input
          className="border rounded-lg px-3 py-2 text-sm w-56"
          placeholder="Buscar templates…"
          value={filterSearch}
          onChange={(e) => setFilterSearch(e.target.value)}
        />
        <select
          className="border rounded-lg px-3 py-2 text-sm"
          value={filterVendor}
          onChange={(e) => setFilterVendor(e.target.value)}
        >
          <option value="">Todos os vendors</option>
          {vendors.map((v) => (
            <option key={v} value={v}>{VENDOR_LABEL[v] ?? v}</option>
          ))}
        </select>
        <select
          className="border rounded-lg px-3 py-2 text-sm"
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
        >
          <option value="">Todas as categorias</option>
          {categories.map((c) => (
            <option key={c} value={c}>{CATEGORY_LABEL[c] ?? c}</option>
          ))}
        </select>
        <div className="ml-auto">
          <button
            onClick={() => { setEditTarget(null); setShowEditor(true); }}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm"
          >
            <Plus size={16} /> Novo Template
          </button>
        </div>
      </div>

      {/* Stats bar */}
      <div className="flex gap-4 mb-6 text-sm text-gray-500">
        <span>{filtered.length} template{filtered.length !== 1 ? "s" : ""}</span>
        <span>·</span>
        <span>{filtered.filter((t) => t.is_system).length} de sistema</span>
        <span>·</span>
        <span>{filtered.filter((t) => !t.is_system).length} personalizados</span>
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="animate-spin text-gray-400" size={32} />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <BookOpen size={48} className="mx-auto mb-3 opacity-30" />
          <p>Nenhum template encontrado</p>
          <p className="text-sm mt-1">Crie um novo template ou ajuste os filtros</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((t) => (
            <TemplateCard
              key={t.id}
              template={t}
              devices={devices}
              onEdit={async () => {
                const full = await goldenTemplateApi.get(t.id);
                setEditTarget(full);
                setShowEditor(true);
              }}
              onDelete={() => {
                if (confirm(`Excluir template "${t.name}"?`)) deleteMut.mutate(t.id);
              }}
            />
          ))}
        </div>
      )}

      {/* Editor modal */}
      {showEditor && (
        <TemplateEditorModal
          initial={editTarget ?? undefined}
          onClose={() => { setShowEditor(false); setEditTarget(null); }}
          onSave={handleSave}
        />
      )}
    </PageWrapper>
  );
}
