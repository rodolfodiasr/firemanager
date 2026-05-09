import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Play, Edit2, Package2, Loader2, ChevronLeft, ChevronRight, X } from "lucide-react";
import { goldenBundlesApi } from "../api/golden_bundles";
import type { GoldenBundle, BundleSection, BundleApply, SectionType, ApplyStrategy, BundleStatus } from "../types/golden_bundle";

type Tab = "biblioteca" | "aplicacoes";

const VENDORS = ["fortinet", "sonicwall", "pfsense", "opnsense"];

const SECTION_TYPES: SectionType[] = [
  "base_config", "objects", "access_rules", "content_filter", "geo_ip", "vpn", "sd_wan",
];

const APPLY_STRATEGIES: ApplyStrategy[] = ["cli_ssh", "rest_api", "manual_only"];

const STATUS_COLORS: Record<BundleStatus, string> = {
  draft: "bg-gray-700 text-gray-300",
  applying: "bg-blue-900/40 text-blue-300",
  applied: "bg-green-900/40 text-green-300",
  failed: "bg-red-900/40 text-red-300",
  rolled_back: "bg-yellow-900/40 text-yellow-300",
};

// ── Apply Modal ────────────────────────────────────────────────────────────────
function ApplyModal({ bundle, onClose }: { bundle: GoldenBundle; onClose: () => void }) {
  const [deviceId, setDeviceId] = useState("");
  const [extraVars, setExtraVars] = useState<Array<{ key: string; value: string }>>([]);
  const [applyResult, setApplyResult] = useState<BundleApply | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const applyMut = useMutation({
    mutationFn: () => {
      const vars = extraVars.reduce<Record<string, string>>((acc, { key, value }) => {
        if (key) acc[key] = value;
        return acc;
      }, {});
      return goldenBundlesApi.apply(bundle.id, deviceId, Object.keys(vars).length ? vars : undefined);
    },
    onSuccess: (data) => {
      setApplyResult(data);
    },
  });

  useEffect(() => {
    if (applyResult && (applyResult.status === "applying" || applyResult.status === "draft")) {
      pollRef.current = setInterval(async () => {
        const updated = await goldenBundlesApi.getApply(applyResult.id);
        setApplyResult(updated);
        if (updated.status !== "applying" && updated.status !== "draft") {
          if (pollRef.current) clearInterval(pollRef.current);
        }
      }, 3000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [applyResult?.id, applyResult?.status]);

  const addVar = () => setExtraVars(v => [...v, { key: "", value: "" }]);
  const removeVar = (i: number) => setExtraVars(v => v.filter((_, idx) => idx !== i));
  const updateVar = (i: number, field: "key" | "value", val: string) =>
    setExtraVars(v => v.map((row, idx) => idx === i ? { ...row, [field]: val } : row));

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-white">Aplicar Bundle: {bundle.name}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">&times;</button>
        </div>

        {!applyResult ? (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Device ID</label>
              <input
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                value={deviceId}
                onChange={e => setDeviceId(e.target.value)}
                placeholder="ID do dispositivo alvo"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-300">Variáveis extras</label>
                <button onClick={addVar} className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1">
                  <Plus size={12} /> Adicionar
                </button>
              </div>
              {extraVars.map((v, i) => (
                <div key={i} className="flex gap-2 mb-2">
                  <input
                    className="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-2 py-1.5 text-white text-xs"
                    placeholder="Chave"
                    value={v.key}
                    onChange={e => updateVar(i, "key", e.target.value)}
                  />
                  <input
                    className="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-2 py-1.5 text-white text-xs"
                    placeholder="Valor"
                    value={v.value}
                    onChange={e => updateVar(i, "value", e.target.value)}
                  />
                  <button onClick={() => removeVar(i)} className="text-red-400 hover:text-red-300 px-1">
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button onClick={onClose} className="px-4 py-2 text-sm border border-gray-600 text-gray-300 rounded-lg hover:bg-gray-700">
                Cancelar
              </button>
              <button
                onClick={() => applyMut.mutate()}
                disabled={applyMut.isPending || !deviceId}
                className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 flex items-center gap-2"
              >
                {applyMut.isPending && <Loader2 size={14} className="animate-spin" />}
                Aplicar
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[applyResult.status]}`}>
                {applyResult.status}
              </span>
              {(applyResult.status === "applying" || applyResult.status === "draft") && (
                <Loader2 size={14} className="animate-spin text-blue-400" />
              )}
            </div>
            {applyResult.section_results && (
              <div>
                <p className="text-sm text-gray-400 mb-2">Resultados por seção:</p>
                <pre className="bg-gray-900 border border-gray-600 rounded-lg p-3 text-xs text-gray-300 overflow-auto max-h-60">
                  {JSON.stringify(applyResult.section_results, null, 2)}
                </pre>
              </div>
            )}
            <div className="flex justify-end">
              <button onClick={onClose} className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium">
                Fechar
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Bundle Wizard ──────────────────────────────────────────────────────────────
type WizardSection = Omit<BundleSection, "id" | "bundle_id">;

function BundleWizard({ bundle, onClose }: { bundle: GoldenBundle | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [step, setStep] = useState(0);

  // Step 1
  const [name, setName] = useState(bundle?.name ?? "");
  const [description, setDescription] = useState(bundle?.description ?? "");
  const [vendor, setVendor] = useState(bundle?.vendor ?? "fortinet");

  // Step 2
  const [variables, setVariables] = useState<Array<{ key: string; value: string }>>(
    bundle ? Object.entries(bundle.variables).map(([key, value]) => ({ key, value })) : []
  );

  // Step 3
  const [sections, setSections] = useState<WizardSection[]>(
    bundle?.sections.map(s => ({
      section_type: s.section_type,
      template_id: s.template_id,
      rest_payload_template: s.rest_payload_template,
      apply_strategy: s.apply_strategy,
      apply_order: s.apply_order,
      rollback_strategy: s.rollback_strategy,
    })) ?? []
  );

  const saveMut = useMutation({
    mutationFn: () => {
      const vars = variables.reduce<Record<string, string>>((acc, { key, value }) => {
        if (key) acc[key] = value;
        return acc;
      }, {});
      const payload = { name, description: description || null, vendor, variables: vars, sections: sections as unknown as BundleSection[] };
      return bundle
        ? goldenBundlesApi.update(bundle.id, payload)
        : goldenBundlesApi.create(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["golden-bundles"] });
      onClose();
    },
  });

  const addVar = () => setVariables(v => [...v, { key: "", value: "" }]);
  const removeVar = (i: number) => setVariables(v => v.filter((_, idx) => idx !== i));
  const updateVar = (i: number, field: "key" | "value", val: string) =>
    setVariables(v => v.map((row, idx) => idx === i ? { ...row, [field]: val } : row));

  const addSection = () => setSections(s => [...s, {
    section_type: "base_config",
    template_id: null,
    rest_payload_template: null,
    apply_strategy: "cli_ssh",
    apply_order: s.length + 1,
    rollback_strategy: "none",
  }]);
  const removeSection = (i: number) => setSections(s => s.filter((_, idx) => idx !== i));
  const updateSection = (i: number, field: keyof WizardSection, val: unknown) =>
    setSections(s => s.map((row, idx) => idx === i ? { ...row, [field]: val } : row));

  const STEPS = ["Info Básica", "Variáveis", "Seções"];

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between mb-4 flex-shrink-0">
          <h2 className="text-lg font-semibold text-white">{bundle ? "Editar Bundle" : "Novo Bundle"}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">&times;</button>
        </div>

        {/* Step indicator */}
        <div className="flex gap-2 mb-5 flex-shrink-0">
          {STEPS.map((s, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                i < step ? "bg-green-600 text-white" : i === step ? "bg-brand-600 text-white" : "bg-gray-700 text-gray-400"
              }`}>{i + 1}</div>
              <span className={`text-xs ${i === step ? "text-white" : "text-gray-500"}`}>{s}</span>
              {i < STEPS.length - 1 && <div className="w-6 h-px bg-gray-700 ml-1" />}
            </div>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto space-y-4">
          {step === 0 && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Nome</label>
                <input
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="ex: Filial Padrão Fortinet"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Descrição</label>
                <textarea
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                  rows={3}
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  placeholder="Descreva o bundle..."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Vendor</label>
                <select
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                  value={vendor}
                  onChange={e => setVendor(e.target.value)}
                >
                  {VENDORS.map(v => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
            </>
          )}

          {step === 1 && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm text-gray-400">Defina as variáveis globais do bundle</p>
                <button onClick={addVar} className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1">
                  <Plus size={12} /> Adicionar
                </button>
              </div>
              {variables.length === 0 && (
                <p className="text-center text-gray-600 text-sm py-8">Nenhuma variável. Clique em Adicionar.</p>
              )}
              {variables.map((v, i) => (
                <div key={i} className="flex gap-2 mb-2">
                  <input
                    className="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-2 py-1.5 text-white text-sm font-mono"
                    placeholder="NOME_VARIAVEL"
                    value={v.key}
                    onChange={e => updateVar(i, "key", e.target.value)}
                  />
                  <input
                    className="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-2 py-1.5 text-white text-sm"
                    placeholder="valor padrão"
                    value={v.value}
                    onChange={e => updateVar(i, "value", e.target.value)}
                  />
                  <button onClick={() => removeVar(i)} className="text-red-400 hover:text-red-300 px-1">
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {step === 2 && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm text-gray-400">Configure as seções do bundle</p>
                <button onClick={addSection} className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1">
                  <Plus size={12} /> Adicionar Seção
                </button>
              </div>
              {sections.length === 0 && (
                <p className="text-center text-gray-600 text-sm py-8">Nenhuma seção. Clique em Adicionar Seção.</p>
              )}
              {sections.map((s, i) => (
                <div key={i} className="bg-gray-750 border border-gray-700 rounded-lg p-4 mb-3">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium text-gray-300">Seção {i + 1}</span>
                    <button onClick={() => removeSection(i)} className="text-red-400 hover:text-red-300">
                      <Trash2 size={14} />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Tipo</label>
                      <select
                        className="w-full bg-gray-700 border border-gray-600 rounded-lg px-2 py-1.5 text-white text-sm"
                        value={s.section_type}
                        onChange={e => updateSection(i, "section_type", e.target.value as SectionType)}
                      >
                        {SECTION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Estratégia</label>
                      <select
                        className="w-full bg-gray-700 border border-gray-600 rounded-lg px-2 py-1.5 text-white text-sm"
                        value={s.apply_strategy}
                        onChange={e => updateSection(i, "apply_strategy", e.target.value as ApplyStrategy)}
                      >
                        {APPLY_STRATEGIES.map(a => <option key={a} value={a}>{a}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Ordem</label>
                      <input
                        type="number"
                        className="w-full bg-gray-700 border border-gray-600 rounded-lg px-2 py-1.5 text-white text-sm"
                        value={s.apply_order}
                        onChange={e => updateSection(i, "apply_order", parseInt(e.target.value) || 1)}
                        min={1}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Rollback Strategy</label>
                      <input
                        className="w-full bg-gray-700 border border-gray-600 rounded-lg px-2 py-1.5 text-white text-sm"
                        value={s.rollback_strategy}
                        onChange={e => updateSection(i, "rollback_strategy", e.target.value)}
                        placeholder="none"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">REST Payload Template (JSON)</label>
                    <textarea
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-2 py-1.5 text-white text-xs font-mono"
                      rows={4}
                      value={s.rest_payload_template ?? ""}
                      onChange={e => updateSection(i, "rest_payload_template", e.target.value || null)}
                      placeholder='{"name": "{DEVICE_NAME}", ...}'
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-between pt-4 mt-4 border-t border-gray-700 flex-shrink-0">
          <button
            onClick={() => setStep(s => s - 1)}
            disabled={step === 0}
            className="flex items-center gap-2 px-4 py-2 text-sm border border-gray-600 text-gray-300 rounded-lg hover:bg-gray-700 disabled:opacity-30"
          >
            <ChevronLeft size={16} /> Anterior
          </button>
          {step < STEPS.length - 1 ? (
            <button
              onClick={() => setStep(s => s + 1)}
              disabled={step === 0 && !name}
              className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            >
              Próximo <ChevronRight size={16} />
            </button>
          ) : (
            <button
              onClick={() => saveMut.mutate()}
              disabled={saveMut.isPending || !name}
              className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            >
              {saveMut.isPending && <Loader2 size={14} className="animate-spin" />}
              Salvar Bundle
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Apply Details Modal ────────────────────────────────────────────────────────
function ApplyDetailsModal({ apply, onClose }: { apply: BundleApply; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Detalhes da Aplicação</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">&times;</button>
        </div>
        <div className="flex items-center gap-3 mb-4">
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[apply.status]}`}>{apply.status}</span>
          <span className="text-gray-400 text-sm">Device: {apply.device_id}</span>
        </div>
        <div className="flex-1 overflow-y-auto">
          <pre className="bg-gray-900 border border-gray-600 rounded-lg p-4 text-xs text-gray-300 whitespace-pre-wrap">
            {JSON.stringify(apply.section_results ?? {}, null, 2)}
          </pre>
        </div>
        <div className="flex justify-end mt-4">
          <button onClick={onClose} className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium">
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export function GoldenBundles() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("biblioteca");
  const [showWizard, setShowWizard] = useState(false);
  const [editingBundle, setEditingBundle] = useState<GoldenBundle | null>(null);
  const [applyingBundle, setApplyingBundle] = useState<GoldenBundle | null>(null);
  const [applyDetails, setApplyDetails] = useState<BundleApply | null>(null);

  // For applies tab we'd need a list endpoint — using local state to track applies initiated in this session
  const [applies, setApplies] = useState<BundleApply[]>([]);

  const { data: bundles = [], isLoading } = useQuery({
    queryKey: ["golden-bundles"],
    queryFn: goldenBundlesApi.list,
  });

  const deleteMut = useMutation({
    mutationFn: goldenBundlesApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["golden-bundles"] }),
  });

  return (
    <div className="ml-64 min-h-screen bg-gray-900">
      <div className="p-6 max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">Golden Bundles</h1>
          <p className="text-sm text-gray-400 mt-1">Biblioteca de configurações completas por vendor</p>
        </div>

        <div className="flex gap-1 mb-6 border-b border-gray-700">
          {([
            ["biblioteca", "Biblioteca", Package2],
            ["aplicacoes", "Aplicações", Play],
          ] as const).map(([key, label, Icon]) => (
            <button
              key={key}
              onClick={() => setTab(key as Tab)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === key
                  ? "border-brand-500 text-brand-400"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              <Icon size={16} />{label}
            </button>
          ))}
        </div>

        {tab === "biblioteca" && (
          <div>
            <div className="flex justify-end mb-4">
              <button
                onClick={() => { setEditingBundle(null); setShowWizard(true); }}
                className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
              >
                <Plus size={16} /> Novo Bundle
              </button>
            </div>

            {isLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="animate-spin text-brand-500" size={24} />
              </div>
            ) : bundles.length === 0 ? (
              <div className="text-center py-16 text-gray-500">
                <Package2 size={40} className="mx-auto mb-3 opacity-30" />
                <p>Nenhum bundle criado</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {bundles.map((b: GoldenBundle) => (
                  <div key={b.id} className="bg-gray-800 rounded-xl border border-gray-700 p-6 flex flex-col gap-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-white font-semibold truncate">{b.name}</h3>
                        {b.description && (
                          <p className="text-gray-400 text-xs mt-1 line-clamp-2">{b.description}</p>
                        )}
                      </div>
                      <span className="ml-2 flex-shrink-0 px-2 py-0.5 rounded text-xs font-medium bg-blue-900/40 text-blue-300">
                        {b.vendor}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500">
                      {b.sections.length} seção{b.sections.length !== 1 ? "ões" : ""}
                    </div>
                    <div className="flex items-center gap-2 mt-auto pt-2 border-t border-gray-700">
                      <button
                        onClick={() => setApplyingBundle(b)}
                        className="flex items-center gap-1 text-xs text-green-400 hover:text-green-300"
                      >
                        <Play size={12} /> Aplicar
                      </button>
                      <button
                        onClick={() => { setEditingBundle(b); setShowWizard(true); }}
                        className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                      >
                        <Edit2 size={12} /> Editar
                      </button>
                      <button
                        onClick={() => { if (confirm("Excluir bundle?")) deleteMut.mutate(b.id); }}
                        className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 ml-auto"
                      >
                        <Trash2 size={12} /> Excluir
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "aplicacoes" && (
          <div className="bg-gray-800 rounded-xl border border-gray-700">
            {applies.length === 0 ? (
              <div className="text-center py-16 text-gray-500">
                <Play size={40} className="mx-auto mb-3 opacity-30" />
                <p>Nenhuma aplicação registrada nesta sessão</p>
                <p className="text-xs mt-1 text-gray-600">Aplique um bundle na aba Biblioteca</p>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="text-left py-2 px-3 text-gray-400 font-medium">Bundle ID</th>
                    <th className="text-left py-2 px-3 text-gray-400 font-medium">Device</th>
                    <th className="text-left py-2 px-3 text-gray-400 font-medium">Status</th>
                    <th className="text-left py-2 px-3 text-gray-400 font-medium">Iniciado</th>
                    <th className="text-left py-2 px-3 text-gray-400 font-medium">Concluído</th>
                    <th className="text-left py-2 px-3 text-gray-400 font-medium">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {applies.map(a => (
                    <tr key={a.id} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                      <td className="py-2 px-3 font-mono text-xs text-gray-300">{a.bundle_id.slice(0, 8)}...</td>
                      <td className="py-2 px-3 text-gray-300">{a.device_id}</td>
                      <td className="py-2 px-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[a.status]}`}>
                          {a.status}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-gray-400 text-xs">
                        {new Date(a.started_at).toLocaleString("pt-BR")}
                      </td>
                      <td className="py-2 px-3 text-gray-400 text-xs">
                        {a.completed_at ? new Date(a.completed_at).toLocaleString("pt-BR") : "—"}
                      </td>
                      <td className="py-2 px-3">
                        <button
                          onClick={() => setApplyDetails(a)}
                          className="text-xs text-blue-400 hover:text-blue-300"
                        >
                          Ver Detalhes
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {showWizard && (
        <BundleWizard
          bundle={editingBundle}
          onClose={() => { setShowWizard(false); setEditingBundle(null); }}
        />
      )}
      {applyingBundle && (
        <ApplyModal
          bundle={applyingBundle}
          onClose={() => setApplyingBundle(null)}
        />
      )}
      {applyDetails && (
        <ApplyDetailsModal apply={applyDetails} onClose={() => setApplyDetails(null)} />
      )}
    </div>
  );
}
