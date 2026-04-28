import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Pencil, X, Check, Globe, Server, ChevronDown, Tag, AlertTriangle } from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { variablesApi } from "../api/variables";
import { devicesApi } from "../api/devices";
import type { TenantVariable, DeviceVariable, VariableType, VariableFormData } from "../types/variable";
import type { Device } from "../types/device";
import { VARIABLE_TYPE_LABELS } from "../types/variable";

// ── Helpers ───────────────────────────────────────────────────────────────────

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

const EMPTY_FORM: VariableFormData = {
  name: "", value: "", variable_type: "string", description: "",
};

// ── Variable Form Modal ───────────────────────────────────────────────────────

interface VarModalProps {
  initial?: VariableFormData;
  onSave: (data: VariableFormData) => void;
  onClose: () => void;
  isLoading: boolean;
  title: string;
  nameReadOnly?: boolean;
}

function VarModal({ initial = EMPTY_FORM, onSave, onClose, isLoading, title, nameReadOnly }: VarModalProps) {
  const [form, setForm] = useState<VariableFormData>(initial);
  const set = (k: keyof VariableFormData, v: string) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h3 className="text-base font-semibold text-gray-900">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Nome <span className="text-gray-400 font-normal">(use em mensagens como <code className="bg-gray-100 px-1 rounded">{`{{nome}}`}</code>)</span>
            </label>
            <input
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              disabled={nameReadOnly}
              placeholder="rede_local"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-gray-50 disabled:text-gray-500 font-mono"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Tipo</label>
            <select
              value={form.variable_type}
              onChange={(e) => set("variable_type", e.target.value as VariableType)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {(Object.keys(VARIABLE_TYPE_LABELS) as VariableType[]).map((t) => (
                <option key={t} value={t}>{VARIABLE_TYPE_LABELS[t]}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Valor</label>
            <input
              value={form.value}
              onChange={(e) => set("value", e.target.value)}
              placeholder={form.variable_type === "network" ? "192.168.1.0/24" : form.variable_type === "port" ? "443" : "valor"}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Descrição <span className="text-gray-400 font-normal">(opcional)</span></label>
            <input
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
              placeholder="Rede local da filial principal"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
        </div>
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">
            Cancelar
          </button>
          <button
            onClick={() => onSave(form)}
            disabled={isLoading || !form.name.trim() || !form.value.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 rounded-lg disabled:opacity-50 flex items-center gap-2"
          >
            {isLoading ? <span className="animate-spin border-2 border-white border-t-transparent rounded-full w-3 h-3" /> : <Check size={14} />}
            Salvar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Variable Row ──────────────────────────────────────────────────────────────

interface VarRowProps {
  name: string;
  value: string;
  type: VariableType;
  description?: string | null;
  badge?: React.ReactNode;
  onEdit: () => void;
  onDelete: () => void;
}

function VarRow({ name, value, type, description, badge, onEdit, onDelete }: VarRowProps) {
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
        <button onClick={onEdit} className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-brand-50 rounded-md">
          <Pencil size={13} />
        </button>
        <button onClick={onDelete} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md">
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  );
}

// ── Tenant Variables Tab ──────────────────────────────────────────────────────

function TenantVarsTab() {
  const qc = useQueryClient();
  const [modal, setModal] = useState<{ open: boolean; editing?: TenantVariable }>({ open: false });

  const { data: vars = [], isLoading } = useQuery({
    queryKey: ["tenant-variables"],
    queryFn: variablesApi.listTenant,
  });

  const createMut = useMutation({
    mutationFn: (d: VariableFormData) =>
      variablesApi.createTenant({ name: d.name, value: d.value, variable_type: d.variable_type, description: d.description || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["tenant-variables"] }); setModal({ open: false }); toast.success("Variável criada"); },
    onError: () => toast.error("Erro ao criar variável. Verifique se o nome já existe."),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, d }: { id: string; d: VariableFormData }) =>
      variablesApi.updateTenant(id, { value: d.value, variable_type: d.variable_type, description: d.description || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["tenant-variables"] }); setModal({ open: false }); toast.success("Variável atualizada"); },
    onError: () => toast.error("Erro ao atualizar variável"),
  });

  const deleteMut = useMutation({
    mutationFn: variablesApi.deleteTenant,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["tenant-variables"] }); toast.success("Variável removida"); },
    onError: () => toast.error("Erro ao remover variável"),
  });

  const handleSave = (d: VariableFormData) => {
    if (modal.editing) updateMut.mutate({ id: modal.editing.id, d });
    else createMut.mutate(d);
  };

  const isBusy = createMut.isPending || updateMut.isPending;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">
          Valem para todos os dispositivos. Podem ser sobrescritas por variável específica do device.
        </p>
        <button
          onClick={() => setModal({ open: true })}
          className="flex items-center gap-2 px-3 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm rounded-lg font-medium"
        >
          <Plus size={14} /> Nova variável global
        </button>
      </div>

      {isLoading ? (
        <p className="text-sm text-gray-400 py-8 text-center">Carregando...</p>
      ) : vars.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <Globe size={32} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">Nenhuma variável global cadastrada.</p>
          <p className="text-xs mt-1">Crie variáveis como <code className="bg-gray-100 px-1 rounded">{`{{dns}}`}</code> ou <code className="bg-gray-100 px-1 rounded">{`{{ntp_server}}`}</code> que valem para todos os firewalls.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
          {vars.map((v) => (
            <VarRow
              key={v.id}
              name={v.name} value={v.value} type={v.variable_type} description={v.description}
              onEdit={() => setModal({ open: true, editing: v })}
              onDelete={() => { if (confirm(`Remover variável {{${v.name}}}?`)) deleteMut.mutate(v.id); }}
            />
          ))}
        </div>
      )}

      {modal.open && (
        <VarModal
          title={modal.editing ? "Editar variável global" : "Nova variável global"}
          initial={modal.editing ? { name: modal.editing.name, value: modal.editing.value, variable_type: modal.editing.variable_type, description: modal.editing.description ?? "" } : EMPTY_FORM}
          nameReadOnly={!!modal.editing}
          onSave={handleSave}
          onClose={() => setModal({ open: false })}
          isLoading={isBusy}
        />
      )}
    </div>
  );
}

// ── Device Variables Tab ──────────────────────────────────────────────────────

function DeviceVarsTab() {
  const qc = useQueryClient();
  const [selectedDevice, setSelectedDevice] = useState<string>("");
  const [modal, setModal] = useState<{ open: boolean; editing?: DeviceVariable }>({ open: false });

  const { data: devices = [] } = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.list,
  });

  const { data: vars = [], isLoading } = useQuery({
    queryKey: ["device-variables", selectedDevice],
    queryFn: () => variablesApi.listDevice(selectedDevice),
    enabled: !!selectedDevice,
  });

  const createMut = useMutation({
    mutationFn: (d: VariableFormData) =>
      variablesApi.createDevice(selectedDevice, { name: d.name, value: d.value, variable_type: d.variable_type, description: d.description || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["device-variables", selectedDevice] }); setModal({ open: false }); toast.success("Variável criada"); },
    onError: () => toast.error("Erro ao criar variável. Verifique se o nome já existe neste device."),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, d }: { id: string; d: VariableFormData }) =>
      variablesApi.updateDevice(selectedDevice, id, { value: d.value, variable_type: d.variable_type, description: d.description || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["device-variables", selectedDevice] }); setModal({ open: false }); toast.success("Variável atualizada"); },
    onError: () => toast.error("Erro ao atualizar variável"),
  });

  const deleteMut = useMutation({
    mutationFn: (varId: string) => variablesApi.deleteDevice(selectedDevice, varId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["device-variables", selectedDevice] }); toast.success("Variável removida"); },
    onError: () => toast.error("Erro ao remover variável"),
  });

  const handleSave = (d: VariableFormData) => {
    if (modal.editing) updateMut.mutate({ id: modal.editing.id, d });
    else createMut.mutate(d);
  };

  const isBusy = createMut.isPending || updateMut.isPending;
  const selectedDev = devices.find((d) => d.id === selectedDevice);

  return (
    <div>
      {/* Device selector */}
      <div className="mb-5">
        <label className="block text-xs font-medium text-gray-700 mb-1">Selecione o dispositivo</label>
        <div className="relative max-w-sm">
          <select
            value={selectedDevice}
            onChange={(e) => setSelectedDevice(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-brand-500 pr-8"
          >
            <option value="">-- escolha um device --</option>
            {devices.map((d) => (
              <option key={d.id} value={d.id}>{d.name} ({d.vendor})</option>
            ))}
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
              Variáveis de <span className="font-medium text-gray-700">{selectedDev?.name}</span>.
              {" "}Sobrescrevem variáveis globais de mesmo nome.
            </p>
            <button
              onClick={() => setModal({ open: true })}
              className="flex items-center gap-2 px-3 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm rounded-lg font-medium"
            >
              <Plus size={14} /> Nova variável
            </button>
          </div>

          {isLoading ? (
            <p className="text-sm text-gray-400 py-8 text-center">Carregando...</p>
          ) : vars.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <Tag size={32} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">Nenhuma variável específica cadastrada para este device.</p>
              <p className="text-xs mt-1">Crie variáveis como <code className="bg-gray-100 px-1 rounded">{`{{rede_local}}`}</code> com o valor específico desta unidade.</p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
              {vars.map((v) => (
                <VarRow
                  key={v.id}
                  name={v.name} value={v.value} type={v.variable_type} description={v.description}
                  badge={
                    v.overrides_tenant ? (
                      <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                        sobrescreve global
                      </span>
                    ) : undefined
                  }
                  onEdit={() => setModal({ open: true, editing: v })}
                  onDelete={() => { if (confirm(`Remover variável {{${v.name}}} deste device?`)) deleteMut.mutate(v.id); }}
                />
              ))}
            </div>
          )}
        </>
      )}

      {modal.open && (
        <VarModal
          title={modal.editing ? "Editar variável do device" : "Nova variável do device"}
          initial={modal.editing ? { name: modal.editing.name, value: modal.editing.value, variable_type: modal.editing.variable_type, description: modal.editing.description ?? "" } : EMPTY_FORM}
          nameReadOnly={!!modal.editing}
          onSave={handleSave}
          onClose={() => setModal({ open: false })}
          isLoading={isBusy}
        />
      )}
    </div>
  );
}

// ── Preview Tab ───────────────────────────────────────────────────────────────

function PreviewTab() {
  const [text, setText] = useState("");
  const [deviceIds, setDeviceIds] = useState<string[]>([]);
  const [result, setResult] = useState<import("../types/variable").BulkJobPreviewResponse | null>(null);

  const { data: devices = [] } = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.list,
  });

  const previewMut = useMutation({
    mutationFn: variablesApi.preview,
    onSuccess: (data) => setResult(data),
    onError: () => toast.error("Erro ao gerar preview"),
  });

  const toggleDevice = (id: string) =>
    setDeviceIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  const canPreview = text.trim().length > 0 && deviceIds.length > 0;

  return (
    <div className="space-y-5">
      <p className="text-sm text-gray-500">
        Simule como as variáveis serão resolvidas para cada device <strong>sem criar o job</strong>.
        Ideal para validar antes de um deploy em massa.
      </p>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Texto com variáveis</label>
        <textarea
          rows={3}
          value={text}
          onChange={(e) => { setText(e.target.value); setResult(null); }}
          placeholder={`Crie uma regra liberando {{rede_local}} para {{dns}} na porta 53`}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
        />
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

      <button
        onClick={() => previewMut.mutate({ device_ids: deviceIds, natural_language_input: text })}
        disabled={!canPreview || previewMut.isPending}
        className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm rounded-lg disabled:opacity-50 font-medium"
      >
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

// ── Main Page ─────────────────────────────────────────────────────────────────

type Tab = "global" | "device" | "preview";

export function Variables() {
  const [tab, setTab] = useState<Tab>("global");

  const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: "global",  label: "Variáveis Globais", icon: Globe },
    { id: "device",  label: "Por Dispositivo",   icon: Server },
    { id: "preview", label: "Preview / Dry-run", icon: Check },
  ];

  return (
    <PageWrapper title="Variáveis">
      <div className="max-w-4xl mx-auto">
        {/* Info banner */}
        <div className="bg-brand-50 border border-brand-200 rounded-xl p-4 mb-6 text-sm text-brand-700">
          <p className="font-semibold mb-1">Como usar variáveis</p>
          <p>
            Use <code className="bg-white px-1 rounded border border-brand-200">{`{{nome_variavel}}`}</code> em qualquer mensagem para o agente ou operação em lote.
            O sistema substitui automaticamente pelo valor correto de cada device antes de enviar ao AI.
          </p>
          <p className="mt-1 text-brand-600">
            Exemplo: <code className="bg-white px-1 rounded border border-brand-200">{`Libere {{rede_local}} para {{dns}} na porta 53`}</code>
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1 mb-6">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                tab === id ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {tab === "global"  && <TenantVarsTab />}
        {tab === "device"  && <DeviceVarsTab />}
        {tab === "preview" && <PreviewTab />}
      </div>
    </PageWrapper>
  );
}
