import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Shield, FileCheck2, ClipboardList, Activity, Plus, ChevronRight,
  CheckCircle, XCircle, AlertTriangle, Clock, RotateCcw, Wrench,
} from "lucide-react";
import {
  complianceEnterpriseApi,
  type Assessment, type BcdrPlan, type CompliancePack, type SlaConfig,
} from "../api/complianceEnterprise";

type Tab = "packs" | "assessments" | "bcdr" | "sla";

// ── helpers ──────────────────────────────────────────────────────────────────
const SEV_COLORS: Record<string, string> = {
  critical: "bg-red-900/50 text-red-300",
  high: "bg-orange-900/50 text-orange-300",
  medium: "bg-yellow-900/50 text-yellow-300",
  low: "bg-gray-700 text-gray-300",
};
const STATUS_ICON: Record<string, JSX.Element> = {
  compliant: <CheckCircle size={14} className="text-green-400" />,
  partial: <AlertTriangle size={14} className="text-yellow-400" />,
  non_compliant: <XCircle size={14} className="text-red-400" />,
  not_evaluated: <Clock size={14} className="text-gray-500" />,
};
const FW_LABELS: Record<string, string> = {
  cis_l1: "CIS L1", cis_l2: "CIS L2", pci_dss: "PCI-DSS",
  lgpd: "LGPD", bacen: "BACEN", iso_27001: "ISO 27001",
};

// ── PacksTab ─────────────────────────────────────────────────────────────────
function PacksTab({ onStart }: { onStart: (pack: CompliancePack) => void }) {
  const qc = useQueryClient();
  const { data: packs = [], isLoading } = useQuery({ queryKey: ["ce-packs"], queryFn: complianceEnterpriseApi.listPacks });
  const seedMut = useMutation({
    mutationFn: complianceEnterpriseApi.seedPacks,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ce-packs"] }),
  });

  if (isLoading) return <p className="text-gray-400 py-8 text-center">Carregando...</p>;

  return (
    <div className="space-y-4">
      {packs.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-400 mb-4">Nenhum pack disponível. Carregue os packs padrão.</p>
          <button onClick={() => seedMut.mutate()} disabled={seedMut.isPending}
            className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
            {seedMut.isPending ? "Carregando..." : "Carregar Packs Padrão (CIS · PCI-DSS · LGPD · BACEN)"}
          </button>
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {packs.map(pack => (
          <div key={pack.id} className="bg-gray-800 border border-gray-700 rounded-xl p-5">
            <div className="flex items-start justify-between mb-3">
              <div>
                <span className="text-xs font-mono bg-brand-900/50 text-brand-300 px-2 py-0.5 rounded">
                  {FW_LABELS[pack.framework] ?? pack.framework}
                </span>
                {pack.version && <span className="text-xs text-gray-500 ml-2">{pack.version}</span>}
              </div>
              {pack.is_builtin && <span className="text-xs text-gray-500">Padrão</span>}
            </div>
            <h3 className="text-white font-semibold mb-1">{pack.name}</h3>
            <p className="text-gray-400 text-sm mb-4 line-clamp-2">{pack.description}</p>
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">{pack.control_count} controles</span>
              <button onClick={() => onStart(pack)}
                className="flex items-center gap-1 bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg text-sm">
                Iniciar Assessment <ChevronRight size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── AssessmentsTab ────────────────────────────────────────────────────────────
function AssessmentsTab() {
  const [selected, setSelected] = useState<Assessment | null>(null);
  const qc = useQueryClient();
  const { data: items = [] } = useQuery({ queryKey: ["ce-assessments"], queryFn: complianceEnterpriseApi.listAssessments });

  const completeMut = useMutation({
    mutationFn: (id: string) => complianceEnterpriseApi.completeAssessment(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ce-assessments"] }); setSelected(null); },
  });

  const findingMut = useMutation<Assessment, Error, { id: string; control_id: string; status: string; evidence: string; notes: string }>({
    mutationFn: ({ id, ...rest }) =>
      complianceEnterpriseApi.updateFinding(id, rest),
    onSuccess: (data) => setSelected(data),
  });

  if (selected) {
    const findings = selected.findings ?? [];
    return (
      <div>
        <div className="flex items-center justify-between mb-4">
          <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-white text-sm">← Voltar</button>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-400">{selected.pack_name} — {selected.name}</span>
            {selected.status === "in_progress" && (
              <button onClick={() => completeMut.mutate(selected.id)} disabled={completeMut.isPending}
                className="bg-green-700 hover:bg-green-800 text-white px-3 py-1.5 rounded-lg text-sm">
                Concluir Assessment
              </button>
            )}
          </div>
        </div>
        {selected.status === "completed" && (
          <div className="bg-gray-800 rounded-xl p-4 mb-4 flex items-center gap-6">
            <div>
              <div className={`text-3xl font-bold ${(selected.overall_score ?? 0) >= 75 ? "text-green-400" : (selected.overall_score ?? 0) >= 50 ? "text-yellow-400" : "text-red-400"}`}>
                {selected.overall_score?.toFixed(1)}%
              </div>
              <div className="text-xs text-gray-400">Score geral</div>
            </div>
            <div className="text-sm text-gray-300 space-y-1">
              <div className="flex items-center gap-2"><CheckCircle size={14} className="text-green-400" /> {selected.compliant_count} conformes</div>
              <div className="flex items-center gap-2"><AlertTriangle size={14} className="text-yellow-400" /> {selected.partial_count} parciais</div>
              <div className="flex items-center gap-2"><XCircle size={14} className="text-red-400" /> {selected.non_compliant_count} não conformes</div>
            </div>
          </div>
        )}
        <div className="space-y-2">
          {findings.map(f => (
            <div key={f.control_id} className="bg-gray-800 border border-gray-700 rounded-lg p-4">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <span className="text-xs text-gray-500 font-mono mr-2">{f.control_id}</span>
                  <span className="text-white text-sm">{f.title}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${SEV_COLORS[f.severity] ?? SEV_COLORS.medium}`}>{f.severity}</span>
                  {STATUS_ICON[f.status]}
                </div>
              </div>
              {selected.status === "in_progress" && (
                <div className="mt-2 grid grid-cols-3 gap-2">
                  {["compliant","partial","non_compliant"].map(s => (
                    <button key={s} onClick={() => findingMut.mutate({ id: selected.id, control_id: f.control_id, status: s, evidence: f.evidence, notes: f.notes })}
                      className={`text-xs py-1 px-2 rounded border ${f.status === s ? "bg-brand-600 border-brand-500 text-white" : "border-gray-600 text-gray-400 hover:border-brand-500"}`}>
                      {s === "compliant" ? "Conforme" : s === "partial" ? "Parcial" : "Não conforme"}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {items.length === 0 && <p className="text-gray-400 text-center py-8">Nenhum assessment. Inicie um na aba Packs.</p>}
      {items.map(a => (
        <div key={a.id} onClick={() => setSelected(a)}
          className="bg-gray-800 border border-gray-700 rounded-xl p-4 cursor-pointer hover:border-brand-500 transition-colors flex items-center justify-between">
          <div>
            <div className="text-white font-medium">{a.name}</div>
            <div className="text-xs text-gray-400">{a.pack_name} · {new Date(a.started_at).toLocaleDateString("pt-BR")}</div>
          </div>
          <div className="flex items-center gap-4">
            {a.status === "completed" && <span className="text-lg font-bold text-green-400">{a.overall_score?.toFixed(1)}%</span>}
            <span className={`text-xs px-2 py-0.5 rounded ${a.status === "completed" ? "bg-green-900/50 text-green-300" : "bg-yellow-900/50 text-yellow-300"}`}>
              {a.status === "completed" ? "Concluído" : "Em andamento"}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── BcdrTab ───────────────────────────────────────────────────────────────────
function BcdrTab() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<{ name: string; description: string; rto_hours: number; rpo_hours: number; scope: string; status: "draft" | "active" | "archived" }>({ name: "", description: "", rto_hours: 4, rpo_hours: 1, scope: "", status: "draft" });

  const { data: plans = [] } = useQuery({ queryKey: ["ce-bcdr"], queryFn: complianceEnterpriseApi.listBcdr });
  const createMut = useMutation({
    mutationFn: (data: typeof form) => complianceEnterpriseApi.createBcdr(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ce-bcdr"] }); setShowForm(false); },
  });
  const testMut = useMutation({
    mutationFn: ({ id, result }: { id: string; result: string }) =>
      complianceEnterpriseApi.recordTest(id, result, "Teste registrado manualmente"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ce-bcdr"] }),
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => complianceEnterpriseApi.deleteBcdr(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ce-bcdr"] }),
  });

  const TEST_RESULT_COLORS: Record<string, string> = {
    passed: "text-green-400", failed: "text-red-400", partial: "text-yellow-400",
  };

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button onClick={() => setShowForm(true)} className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
          <Plus size={16} /> Novo Plano BC/DR
        </button>
      </div>
      {showForm && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-5 mb-4">
          <h3 className="text-white font-semibold mb-4">Novo Plano BC/DR</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="col-span-2">
              <label className="text-xs text-gray-400 block mb-1">Nome do Plano</label>
              <input value={form.name} onChange={e => setForm({...form, name: e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">RTO (horas)</label>
              <input type="number" value={form.rto_hours} onChange={e => setForm({...form, rto_hours: +e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">RPO (horas)</label>
              <input type="number" value={form.rpo_hours} onChange={e => setForm({...form, rpo_hours: +e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-gray-400 block mb-1">Escopo</label>
              <textarea value={form.scope} onChange={e => setForm({...form, scope: e.target.value})} rows={2}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-white px-4 py-2 text-sm">Cancelar</button>
            <button onClick={() => createMut.mutate(form)} disabled={!form.name || createMut.isPending}
              className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
              {createMut.isPending ? "Criando..." : "Criar"}
            </button>
          </div>
        </div>
      )}
      <div className="space-y-3">
        {plans.map(plan => (
          <div key={plan.id} className="bg-gray-800 border border-gray-700 rounded-xl p-5">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-white font-semibold">{plan.name}</h3>
                {plan.scope && <p className="text-gray-400 text-sm mt-1">{plan.scope}</p>}
              </div>
              <span className={`text-xs px-2 py-0.5 rounded ${plan.status === "active" ? "bg-green-900/50 text-green-300" : plan.status === "archived" ? "bg-gray-700 text-gray-400" : "bg-yellow-900/50 text-yellow-300"}`}>
                {plan.status}
              </span>
            </div>
            <div className="flex items-center gap-6 text-sm text-gray-300 mb-4">
              <div><span className="text-gray-500 text-xs">RTO</span> <span className="font-bold text-brand-400">{plan.rto_hours}h</span></div>
              <div><span className="text-gray-500 text-xs">RPO</span> <span className="font-bold text-brand-400">{plan.rpo_hours}h</span></div>
              {plan.last_test_at && (
                <div>
                  <span className="text-gray-500 text-xs">Último teste</span>{" "}
                  <span className={`font-medium ${TEST_RESULT_COLORS[plan.last_test_result ?? ""] ?? "text-gray-300"}`}>
                    {plan.last_test_result} · {new Date(plan.last_test_at).toLocaleDateString("pt-BR")}
                  </span>
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <button onClick={() => testMut.mutate({ id: plan.id, result: "passed" })}
                className="flex items-center gap-1 text-xs bg-green-800 hover:bg-green-700 text-white px-3 py-1.5 rounded-lg">
                <RotateCcw size={12} /> Registrar Teste ✓
              </button>
              <button onClick={() => testMut.mutate({ id: plan.id, result: "failed" })}
                className="flex items-center gap-1 text-xs bg-red-800 hover:bg-red-700 text-white px-3 py-1.5 rounded-lg">
                <RotateCcw size={12} /> Registrar Teste ✗
              </button>
              <button onClick={() => { if (confirm("Excluir plano?")) deleteMut.mutate(plan.id); }}
                className="text-xs text-red-400 hover:text-red-300 px-3 py-1.5">Excluir</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── SlaTab ────────────────────────────────────────────────────────────────────
function SlaTab() {
  const qc = useQueryClient();
  const { data: slas = [] } = useQuery({ queryKey: ["ce-sla"], queryFn: complianceEnterpriseApi.getSla });
  const seedMut = useMutation({
    mutationFn: complianceEnterpriseApi.seedSla,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ce-sla"] }),
  });
  const upsertMut = useMutation({
    mutationFn: ({ tier, data }: { tier: string; data: Partial<SlaConfig> }) =>
      complianceEnterpriseApi.upsertSla(tier, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ce-sla"] }),
  });

  const TIER_COLORS: Record<string, string> = {
    critical: "border-red-700", high: "border-orange-700",
    medium: "border-yellow-700", low: "border-gray-600",
  };
  const TIER_LABELS: Record<string, string> = {
    critical: "Crítico", high: "Alto", medium: "Médio", low: "Baixo",
  };

  return (
    <div>
      {slas.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-400 mb-4">Nenhum SLA configurado. Carregue os tiers padrão.</p>
          <button onClick={() => seedMut.mutate()} disabled={seedMut.isPending}
            className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
            {seedMut.isPending ? "Carregando..." : "Carregar SLA Padrão"}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {slas.map(sla => (
            <div key={sla.id} className={`bg-gray-800 border-l-4 rounded-xl p-5 ${TIER_COLORS[sla.tier_name] ?? "border-gray-600"}`}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-white font-semibold">{TIER_LABELS[sla.tier_name] ?? sla.tier_name}</h3>
                <span className={`text-xs px-2 py-0.5 rounded ${sla.is_active ? "bg-green-900/50 text-green-300" : "bg-gray-700 text-gray-400"}`}>
                  {sla.is_active ? "Ativo" : "Inativo"}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div>
                  <div className="text-gray-500 text-xs">Resposta</div>
                  <div className="text-brand-400 font-bold">
                    {sla.response_minutes < 60 ? `${sla.response_minutes}min` : `${sla.response_minutes / 60}h`}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500 text-xs">Resolução</div>
                  <div className="text-brand-400 font-bold">{sla.resolution_hours}h</div>
                </div>
                {sla.escalation_hours && (
                  <div>
                    <div className="text-gray-500 text-xs">Escalação</div>
                    <div className="text-yellow-400 font-bold">{sla.escalation_hours}h</div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function ComplianceEnterprisePage() {
  const [tab, setTab] = useState<Tab>("packs");
  const qc = useQueryClient();
  const [startingPack, setStartingPack] = useState<CompliancePack | null>(null);
  const [assessmentName, setAssessmentName] = useState("");

  const createMut = useMutation({
    mutationFn: () => complianceEnterpriseApi.createAssessment(startingPack!.id, assessmentName || `${startingPack!.name} — ${new Date().toLocaleDateString("pt-BR")}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ce-assessments"] });
      setStartingPack(null);
      setAssessmentName("");
      setTab("assessments");
    },
  });

  const TABS: { id: Tab; label: string; icon: JSX.Element }[] = [
    { id: "packs", label: "Packs de Compliance", icon: <Shield size={16} /> },
    { id: "assessments", label: "Assessments", icon: <ClipboardList size={16} /> },
    { id: "bcdr", label: "Planos BC/DR", icon: <Activity size={16} /> },
    { id: "sla", label: "SLA", icon: <FileCheck2 size={16} /> },
  ];

  return (
    <main className="flex-1 overflow-auto bg-gray-950 p-6">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-1">Compliance Enterprise</h1>
        <p className="text-gray-400 text-sm mb-6">Packs de conformidade, assessments, planos BC/DR e configuração de SLA.</p>

        <div className="flex gap-1 mb-6 bg-gray-800 rounded-xl p-1">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors flex-1 justify-center ${tab === t.id ? "bg-brand-600 text-white" : "text-gray-400 hover:text-white"}`}>
              {t.icon}{t.label}
            </button>
          ))}
        </div>

        {startingPack && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
            <div className="bg-gray-800 rounded-xl p-6 w-full max-w-md border border-gray-700">
              <h3 className="text-white font-semibold mb-4">Iniciar Assessment — {startingPack.name}</h3>
              <input value={assessmentName} onChange={e => setAssessmentName(e.target.value)}
                placeholder="Nome do assessment (ex: Avaliação Q2 2026)"
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm mb-4" />
              <div className="flex justify-end gap-2">
                <button onClick={() => setStartingPack(null)} className="text-gray-400 hover:text-white px-4 py-2 text-sm">Cancelar</button>
                <button onClick={() => createMut.mutate()} disabled={createMut.isPending}
                  className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm">
                  {createMut.isPending ? "Criando..." : "Iniciar"}
                </button>
              </div>
            </div>
          </div>
        )}

        {tab === "packs" && <PacksTab onStart={setStartingPack} />}
        {tab === "assessments" && <AssessmentsTab />}
        {tab === "bcdr" && <BcdrTab />}
        {tab === "sla" && <SlaTab />}
      </div>
    </main>
  );
}
