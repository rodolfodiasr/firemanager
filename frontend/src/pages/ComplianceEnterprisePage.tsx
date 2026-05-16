import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Shield, FileCheck2, Activity, BarChart2, Plus, ChevronDown, ChevronUp,
  CheckCircle, XCircle, AlertTriangle, Clock, RotateCcw, RefreshCw,
  TrendingUp, TrendingDown, Minus,
} from "lucide-react";
import {
  complianceEnterpriseApi,
  type Assessment,
  type BcdrPlan,
  type CompliancePack,
  type ComplianceReport,
  type PackSummaryItem,
  type SlaConfig,
  type SlaReport,
} from "../api/complianceEnterprise";

type Tab = "packs" | "bcdr" | "sla" | "relatorio";

// ── helpers ──────────────────────────────────────────────────────────────────
const SEV_COLORS: Record<string, string> = {
  critical: "bg-red-900/50 text-red-300 border-red-700",
  high: "bg-orange-900/50 text-orange-300 border-orange-700",
  medium: "bg-yellow-900/50 text-yellow-300 border-yellow-700",
  low: "bg-gray-700 text-gray-300 border-gray-600",
};

const STATUS_ICON: Record<string, JSX.Element> = {
  compliant: <CheckCircle size={14} className="text-green-400" />,
  partial: <AlertTriangle size={14} className="text-yellow-400" />,
  non_compliant: <XCircle size={14} className="text-red-400" />,
  not_evaluated: <Clock size={14} className="text-gray-500" />,
  not_applicable: <Minus size={14} className="text-gray-600" />,
};

const STATUS_LABELS: Record<string, string> = {
  compliant: "Conforme",
  partial: "Parcial",
  non_compliant: "Não Conforme",
  not_evaluated: "Não Avaliado",
  not_applicable: "N/A",
};

const FW_LABELS: Record<string, string> = {
  cis_l1: "CIS L1",
  cis_benchmark: "CIS Controls",
  pci_dss: "PCI-DSS",
  lgpd: "LGPD",
  bacen: "BACEN",
  bacen_4658: "BACEN 4.658",
  iso_27001: "ISO 27001",
};

const PACK_TYPES = [
  { value: "cis_benchmark", label: "CIS Controls v8", controls: 15 },
  { value: "pci_dss", label: "PCI-DSS v4.0", controls: 12 },
  { value: "bacen_4658", label: "BACEN 4.658", controls: 8 },
  { value: "lgpd", label: "LGPD", controls: 8 },
];

function ScoreRing({ score }: { score: number }) {
  const color = score >= 75 ? "#22c55e" : score >= 50 ? "#eab308" : "#ef4444";
  return (
    <div className="relative flex items-center justify-center w-20 h-20">
      <svg className="w-20 h-20 -rotate-90" viewBox="0 0 36 36">
        <circle cx="18" cy="18" r="15.9" fill="none" stroke="#374151" strokeWidth="3" />
        <circle
          cx="18" cy="18" r="15.9" fill="none"
          stroke={color} strokeWidth="3"
          strokeDasharray={`${score} ${100 - score}`}
          strokeLinecap="round"
        />
      </svg>
      <span className="absolute text-sm font-bold text-white">{score}%</span>
    </div>
  );
}

// ── Tab 1: Compliance Packs ───────────────────────────────────────────────────
function PacksTab() {
  const qc = useQueryClient();
  const [expandedAssessment, setExpandedAssessment] = useState<string | null>(null);
  const [editingFinding, setEditingFinding] = useState<{ assessmentId: string; controlId: string } | null>(null);
  const [findingEvidence, setFindingEvidence] = useState("");

  const { data: packs = [], isLoading: packsLoading } = useQuery({
    queryKey: ["ce-packs"],
    queryFn: complianceEnterpriseApi.listPacks,
  });

  const { data: summary = [] } = useQuery({
    queryKey: ["ce-summary"],
    queryFn: complianceEnterpriseApi.getPackSummary,
  });

  const { data: assessments = [] } = useQuery({
    queryKey: ["ce-assessments"],
    queryFn: complianceEnterpriseApi.listAssessments,
  });

  const seedTypeMut = useMutation({
    mutationFn: (packType: string) => complianceEnterpriseApi.seedPackByType(packType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ce-packs"] });
      qc.invalidateQueries({ queryKey: ["ce-summary"] });
    },
  });

  const createAssessmentMut = useMutation({
    mutationFn: ({ packId, name }: { packId: string; name: string }) =>
      complianceEnterpriseApi.createAssessment(packId, name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ce-assessments"] });
      qc.invalidateQueries({ queryKey: ["ce-summary"] });
    },
  });

  const findingMut = useMutation({
    mutationFn: ({ assessmentId, controlId, status, evidence }: {
      assessmentId: string; controlId: string; status: string; evidence: string;
    }) => complianceEnterpriseApi.updateFinding(assessmentId, {
      control_id: controlId, status, evidence, notes: "",
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ce-assessments"] });
      qc.invalidateQueries({ queryKey: ["ce-summary"] });
      setEditingFinding(null);
    },
  });

  const completeMut = useMutation({
    mutationFn: (id: string) => complianceEnterpriseApi.completeAssessment(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ce-assessments"] });
      qc.invalidateQueries({ queryKey: ["ce-summary"] });
    },
  });

  const seedAllMut = useMutation({
    mutationFn: complianceEnterpriseApi.seedPacks,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ce-packs"] });
    },
  });

  // Summary by framework
  const summaryByFramework: Record<string, PackSummaryItem> = {};
  for (const s of summary) {
    const key = s.pack_name;
    if (!summaryByFramework[key]) summaryByFramework[key] = s;
  }

  const getAssessmentForPack = (packId: string) =>
    assessments.find(a => String(a.pack_id) === String(packId));

  if (packsLoading) return <p className="text-gray-400 py-8 text-center">Carregando...</p>;

  return (
    <div className="space-y-6">
      {/* Seed controls */}
      <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-white font-semibold text-sm">Frameworks Disponíveis</h3>
          <button
            onClick={() => seedAllMut.mutate()}
            disabled={seedAllMut.isPending}
            className="text-xs text-gray-400 hover:text-white flex items-center gap-1"
          >
            <RefreshCw size={12} /> {seedAllMut.isPending ? "Carregando..." : "Carregar todos"}
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {PACK_TYPES.map(pt => {
            const exists = packs.some(p => p.framework === pt.value);
            return (
              <button
                key={pt.value}
                onClick={() => !exists && seedTypeMut.mutate(pt.value)}
                disabled={exists || seedTypeMut.isPending}
                className={`text-left p-3 rounded-lg border text-sm transition-colors ${
                  exists
                    ? "border-green-700 bg-green-900/20 text-green-300 cursor-default"
                    : "border-gray-600 bg-gray-700 text-gray-300 hover:border-brand-500 hover:text-white cursor-pointer"
                }`}
              >
                <div className="font-semibold">{pt.label}</div>
                <div className="text-xs text-gray-400 mt-0.5">{pt.controls} controles</div>
                {exists && <div className="text-xs text-green-400 mt-1">Carregado</div>}
              </button>
            );
          })}
        </div>
      </div>

      {/* Pack cards grid */}
      {packs.length === 0 ? (
        <p className="text-gray-400 text-center py-8">
          Nenhum pack carregado. Clique nos frameworks acima para iniciar.
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {packs.map(pack => {
            const assessment = getAssessmentForPack(pack.id);
            const sum = summary.find(s => s.pack_name === pack.name);
            const score = sum?.score ?? 0;
            const isExpanded = expandedAssessment === pack.id;

            return (
              <div key={pack.id} className="bg-gray-800 border border-gray-700 rounded-xl p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <span className="text-xs font-mono bg-brand-900/50 text-brand-300 px-2 py-0.5 rounded border border-brand-800">
                      {FW_LABELS[pack.framework] ?? pack.framework}
                    </span>
                    {pack.version && (
                      <span className="text-xs text-gray-500 ml-2">{pack.version}</span>
                    )}
                  </div>
                  {sum && <ScoreRing score={score} />}
                </div>

                <h3 className="text-white font-semibold mb-1">{pack.name}</h3>
                <p className="text-gray-400 text-sm mb-3 line-clamp-2">{pack.description}</p>

                <div className="flex items-center gap-3 text-xs text-gray-400 mb-4">
                  <span>{pack.control_count} controles</span>
                  {sum && (
                    <>
                      <span className="text-green-400">{sum.compliant_count} conformes</span>
                      <span className="text-red-400">{sum.non_compliant_count} não conformes</span>
                    </>
                  )}
                </div>

                <div className="flex gap-2">
                  {!assessment ? (
                    <button
                      onClick={() => createAssessmentMut.mutate({
                        packId: pack.id,
                        name: `${pack.name} — ${new Date().toLocaleDateString("pt-BR")}`,
                      })}
                      disabled={createAssessmentMut.isPending}
                      className="flex-1 bg-brand-600 hover:bg-brand-700 text-white px-3 py-2 rounded-lg text-sm"
                    >
                      Iniciar Avaliação
                    </button>
                  ) : (
                    <button
                      onClick={() => setExpandedAssessment(isExpanded ? null : pack.id)}
                      className="flex-1 flex items-center justify-center gap-2 bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded-lg text-sm"
                    >
                      Ver Controles
                      {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                  )}
                </div>

                {/* Expanded controls list */}
                {isExpanded && assessment && (
                  <div className="mt-4 space-y-2 border-t border-gray-700 pt-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-gray-400 font-medium">
                        {assessment.status === "in_progress" ? "Em andamento" : "Concluído"}
                      </span>
                      {assessment.status === "in_progress" && (
                        <button
                          onClick={() => completeMut.mutate(assessment.id)}
                          disabled={completeMut.isPending}
                          className="text-xs bg-green-700 hover:bg-green-600 text-white px-3 py-1 rounded-lg"
                        >
                          Concluir
                        </button>
                      )}
                    </div>
                    {(assessment.findings ?? []).map(f => (
                      <div key={f.control_id} className="bg-gray-750 border border-gray-600 rounded-lg p-3">
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-xs font-mono text-gray-400">{f.control_id}</span>
                              <span className={`text-xs px-1.5 py-0.5 rounded border ${SEV_COLORS[f.severity] ?? SEV_COLORS.medium}`}>
                                {f.severity}
                              </span>
                            </div>
                            <div className="text-white text-sm mt-0.5 truncate">{f.title}</div>
                          </div>
                          <div className="flex items-center gap-1 ml-2 shrink-0">
                            {STATUS_ICON[f.status] ?? STATUS_ICON.not_evaluated}
                            <span className="text-xs text-gray-400">{STATUS_LABELS[f.status] ?? f.status}</span>
                          </div>
                        </div>

                        {assessment.status === "in_progress" && (
                          <div className="mt-2">
                            {editingFinding?.assessmentId === assessment.id && editingFinding.controlId === f.control_id ? (
                              <div className="space-y-2">
                                <textarea
                                  value={findingEvidence}
                                  onChange={e => setFindingEvidence(e.target.value)}
                                  placeholder="Evidência (opcional)"
                                  rows={2}
                                  className="w-full bg-gray-600 border border-gray-500 rounded px-2 py-1 text-white text-xs"
                                />
                                <div className="flex gap-1 flex-wrap">
                                  {["compliant", "partial", "non_compliant", "not_applicable"].map(s => (
                                    <button
                                      key={s}
                                      onClick={() => findingMut.mutate({
                                        assessmentId: assessment.id,
                                        controlId: f.control_id,
                                        status: s,
                                        evidence: findingEvidence,
                                      })}
                                      className={`text-xs py-1 px-2 rounded border transition-colors ${
                                        f.status === s
                                          ? "bg-brand-600 border-brand-500 text-white"
                                          : "border-gray-600 text-gray-300 hover:border-brand-500"
                                      }`}
                                    >
                                      {STATUS_LABELS[s]}
                                    </button>
                                  ))}
                                  <button
                                    onClick={() => setEditingFinding(null)}
                                    className="text-xs py-1 px-2 text-gray-400 hover:text-white"
                                  >
                                    Fechar
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <button
                                onClick={() => {
                                  setEditingFinding({ assessmentId: assessment.id, controlId: f.control_id });
                                  setFindingEvidence(f.evidence ?? "");
                                }}
                                className="text-xs text-brand-400 hover:text-brand-300"
                              >
                                Editar status
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Tab 2: BC/DR ──────────────────────────────────────────────────────────────
function BcdrTab() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<{
    name: string;
    description: string;
    rto_hours: number;
    rpo_hours: number;
    scope: string;
    status: "draft" | "active" | "archived";
    contacts: string;
    procedures: string;
  }>({
    name: "",
    description: "",
    rto_hours: 4,
    rpo_hours: 1,
    scope: "",
    status: "draft",
    contacts: "",
    procedures: "",
  });

  const { data: plans = [] } = useQuery({
    queryKey: ["ce-bcdr"],
    queryFn: complianceEnterpriseApi.listBcdr,
  });

  const createMut = useMutation({
    mutationFn: () => {
      let contacts = null;
      try {
        contacts = form.contacts ? JSON.parse(form.contacts) : null;
      } catch {
        contacts = form.contacts ? [{ name: form.contacts }] : null;
      }
      return complianceEnterpriseApi.createBcdr({
        name: form.name,
        description: form.description || null,
        rto_hours: form.rto_hours,
        rpo_hours: form.rpo_hours,
        scope: form.scope || null,
        status: form.status,
        contacts,
        recovery_steps: form.procedures ? [{ step: form.procedures, owner: "", duration_minutes: 0 }] : null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ce-bcdr"] });
      setShowForm(false);
      setForm({ name: "", description: "", rto_hours: 4, rpo_hours: 1, scope: "", status: "draft", contacts: "", procedures: "" });
    },
  });

  const testMut = useMutation({
    mutationFn: ({ id, result }: { id: string; result: string }) =>
      complianceEnterpriseApi.recordTest(id, result, "Teste registrado via plataforma"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ce-bcdr"] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => complianceEnterpriseApi.deleteBcdr(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ce-bcdr"] }),
  });

  const STATUS_COLORS: Record<string, string> = {
    active: "bg-green-900/50 text-green-300 border-green-700",
    draft: "bg-yellow-900/50 text-yellow-300 border-yellow-700",
    archived: "bg-gray-700 text-gray-400 border-gray-600",
  };

  const TEST_COLORS: Record<string, string> = {
    passed: "text-green-400",
    failed: "text-red-400",
    partial: "text-yellow-400",
  };

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm"
        >
          <Plus size={16} /> Novo Plano BC/DR
        </button>
      </div>

      {showForm && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-5 mb-4">
          <h3 className="text-white font-semibold mb-4">Novo Plano de Continuidade / Recuperação</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="col-span-2">
              <label className="text-xs text-gray-400 block mb-1">Nome do Plano *</label>
              <input
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                placeholder="ex: Plano de Continuidade — Datacenter Principal"
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">RTO — Recovery Time Objective (horas)</label>
              <input
                type="number" min={0}
                value={form.rto_hours}
                onChange={e => setForm({ ...form, rto_hours: +e.target.value })}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">RPO — Recovery Point Objective (horas)</label>
              <input
                type="number" min={0}
                value={form.rpo_hours}
                onChange={e => setForm({ ...form, rpo_hours: +e.target.value })}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-gray-400 block mb-1">Escopo</label>
              <input
                value={form.scope}
                onChange={e => setForm({ ...form, scope: e.target.value })}
                placeholder="Sistemas e ativos cobertos pelo plano"
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Status</label>
              <select
                value={form.status}
                onChange={e => setForm({ ...form, status: e.target.value as typeof form.status })}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
              >
                <option value="draft">Rascunho</option>
                <option value="active">Ativo</option>
                <option value="archived">Arquivado</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Contatos (JSON ou texto livre)</label>
              <input
                value={form.contacts}
                onChange={e => setForm({ ...form, contacts: e.target.value })}
                placeholder='[{"name":"João","role":"TI Lead","phone":"11 9000-0000"}]'
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm font-mono text-xs"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-gray-400 block mb-1">Procedimentos de Recuperação</label>
              <textarea
                value={form.procedures}
                onChange={e => setForm({ ...form, procedures: e.target.value })}
                rows={3}
                placeholder="Descreva os procedimentos de recuperação de negócio..."
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
              />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setShowForm(false)}
              className="text-gray-400 hover:text-white px-4 py-2 text-sm"
            >
              Cancelar
            </button>
            <button
              onClick={() => createMut.mutate()}
              disabled={!form.name || createMut.isPending}
              className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
            >
              {createMut.isPending ? "Criando..." : "Criar Plano"}
            </button>
          </div>
        </div>
      )}

      {plans.length === 0 && !showForm && (
        <p className="text-gray-400 text-center py-12">
          Nenhum plano BC/DR cadastrado. Crie o primeiro plano acima.
        </p>
      )}

      <div className="space-y-4">
        {plans.map(plan => (
          <div key={plan.id} className="bg-gray-800 border border-gray-700 rounded-xl p-5">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-white font-semibold text-lg">{plan.name}</h3>
                {plan.scope && <p className="text-gray-400 text-sm mt-1">{plan.scope}</p>}
              </div>
              <span className={`text-xs px-2 py-0.5 rounded border ${STATUS_COLORS[plan.status] ?? STATUS_COLORS.draft}`}>
                {plan.status === "active" ? "Ativo" : plan.status === "archived" ? "Arquivado" : "Rascunho"}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div className="bg-gray-750 rounded-lg p-3 border border-gray-600">
                <div className="text-xs text-gray-500 mb-1">RTO</div>
                <div className="text-2xl font-bold text-brand-400">{plan.rto_hours}h</div>
                <div className="text-xs text-gray-500">Recovery Time</div>
              </div>
              <div className="bg-gray-750 rounded-lg p-3 border border-gray-600">
                <div className="text-xs text-gray-500 mb-1">RPO</div>
                <div className="text-2xl font-bold text-brand-400">{plan.rpo_hours}h</div>
                <div className="text-xs text-gray-500">Recovery Point</div>
              </div>
              <div className="bg-gray-750 rounded-lg p-3 border border-gray-600">
                <div className="text-xs text-gray-500 mb-1">Último Teste</div>
                {plan.last_test_at ? (
                  <>
                    <div className={`text-sm font-bold ${TEST_COLORS[plan.last_test_result ?? ""] ?? "text-gray-300"}`}>
                      {plan.last_test_result === "passed" ? "Aprovado" : plan.last_test_result === "failed" ? "Reprovado" : "Parcial"}
                    </div>
                    <div className="text-xs text-gray-500">{new Date(plan.last_test_at).toLocaleDateString("pt-BR")}</div>
                  </>
                ) : (
                  <div className="text-sm text-gray-500">Nunca testado</div>
                )}
              </div>
              <div className="bg-gray-750 rounded-lg p-3 border border-gray-600">
                <div className="text-xs text-gray-500 mb-1">Criado em</div>
                <div className="text-sm text-gray-300">{new Date(plan.created_at).toLocaleDateString("pt-BR")}</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => testMut.mutate({ id: plan.id, result: "passed" })}
                disabled={testMut.isPending}
                className="flex items-center gap-1.5 text-xs bg-green-800 hover:bg-green-700 text-white px-3 py-1.5 rounded-lg"
              >
                <RotateCcw size={12} /> Registrar Teste — Aprovado
              </button>
              <button
                onClick={() => testMut.mutate({ id: plan.id, result: "failed" })}
                disabled={testMut.isPending}
                className="flex items-center gap-1.5 text-xs bg-red-800 hover:bg-red-700 text-white px-3 py-1.5 rounded-lg"
              >
                <RotateCcw size={12} /> Registrar Teste — Reprovado
              </button>
              <button
                onClick={() => testMut.mutate({ id: plan.id, result: "partial" })}
                disabled={testMut.isPending}
                className="flex items-center gap-1.5 text-xs bg-yellow-800 hover:bg-yellow-700 text-white px-3 py-1.5 rounded-lg"
              >
                <RotateCcw size={12} /> Parcial
              </button>
              <button
                onClick={() => {
                  if (confirm(`Excluir o plano "${plan.name}"?`)) deleteMut.mutate(plan.id);
                }}
                className="text-xs text-red-400 hover:text-red-300 px-3 py-1.5 ml-auto"
              >
                Excluir
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Tab 3: SLA ────────────────────────────────────────────────────────────────
function SlaTab() {
  const qc = useQueryClient();
  const [days, setDays] = useState(30);

  const { data: slas = [] } = useQuery({
    queryKey: ["ce-sla"],
    queryFn: complianceEnterpriseApi.getSla,
  });

  const { data: slaReport, isLoading: reportLoading } = useQuery({
    queryKey: ["ce-sla-report", days],
    queryFn: () => complianceEnterpriseApi.getSlaReport(days),
  });

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
    critical: "border-l-red-500",
    high: "border-l-orange-500",
    medium: "border-l-yellow-500",
    low: "border-l-gray-500",
  };

  const TIER_LABELS: Record<string, string> = {
    critical: "Crítico",
    high: "Alto",
    medium: "Médio",
    low: "Baixo",
  };

  return (
    <div className="space-y-6">
      {/* SLA Metrics Report */}
      {slaReport && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-white font-semibold">Métricas do Período</h3>
            <div className="flex items-center gap-2">
              <select
                value={days}
                onChange={e => setDays(+e.target.value)}
                className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-sm"
              >
                <option value={7}>7 dias</option>
                <option value={30}>30 dias</option>
                <option value={90}>90 dias</option>
              </select>
              <span className={`text-xs font-bold px-3 py-1 rounded-full border ${
                slaReport.sla_met
                  ? "bg-green-900/50 text-green-300 border-green-700"
                  : "bg-red-900/50 text-red-300 border-red-700"
              }`}>
                {slaReport.sla_met ? "SLA Atendido" : "SLA Violado"}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-750 rounded-lg p-3 border border-gray-600">
              <div className="text-xs text-gray-500 mb-1">Uptime Estimado</div>
              <div className={`text-2xl font-bold ${
                slaReport.uptime_pct >= slaReport.uptime_target_pct ? "text-green-400" : "text-red-400"
              }`}>
                {slaReport.uptime_pct.toFixed(1)}%
              </div>
              <div className="text-xs text-gray-500">Meta: {slaReport.uptime_target_pct}%</div>
            </div>
            <div className="bg-gray-750 rounded-lg p-3 border border-gray-600">
              <div className="text-xs text-gray-500 mb-1">MTTR Médio</div>
              <div className={`text-2xl font-bold ${
                slaReport.mttr_minutes === 0 || slaReport.mttr_minutes <= slaReport.mttr_target_minutes
                  ? "text-green-400" : "text-red-400"
              }`}>
                {slaReport.mttr_minutes === 0 ? "—" : `${slaReport.mttr_minutes}min`}
              </div>
              <div className="text-xs text-gray-500">Meta: {slaReport.mttr_target_minutes}min</div>
            </div>
            <div className="bg-gray-750 rounded-lg p-3 border border-gray-600">
              <div className="text-xs text-gray-500 mb-1">Total Operações</div>
              <div className="text-2xl font-bold text-white">{slaReport.total_operations}</div>
              <div className="text-xs text-gray-500">{days} dias</div>
            </div>
            <div className="bg-gray-750 rounded-lg p-3 border border-gray-600">
              <div className="text-xs text-gray-500 mb-1">Concluídas</div>
              <div className="text-2xl font-bold text-brand-400">{slaReport.completed_operations}</div>
              <div className="text-xs text-gray-500">de {slaReport.total_operations} total</div>
            </div>
          </div>
        </div>
      )}

      {/* SLA Config */}
      <div>
        {slas.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-400 mb-4">Nenhum SLA configurado. Carregue os tiers padrão.</p>
            <button
              onClick={() => seedMut.mutate()}
              disabled={seedMut.isPending}
              className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm"
            >
              {seedMut.isPending ? "Carregando..." : "Carregar SLA Padrão (Crítico/Alto/Médio/Baixo)"}
            </button>
          </div>
        ) : (
          <>
            <h3 className="text-white font-semibold mb-3">Configuração de SLA por Severidade</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {slas.map(sla => (
                <div key={sla.id} className={`bg-gray-800 border border-gray-700 border-l-4 rounded-xl p-5 ${TIER_COLORS[sla.tier_name] ?? "border-l-gray-500"}`}>
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="text-white font-semibold">{TIER_LABELS[sla.tier_name] ?? sla.tier_name}</h4>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-0.5 rounded ${sla.is_active ? "bg-green-900/50 text-green-300" : "bg-gray-700 text-gray-400"}`}>
                        {sla.is_active ? "Ativo" : "Inativo"}
                      </span>
                      <button
                        onClick={() => upsertMut.mutate({ tier: sla.tier_name, data: { is_active: !sla.is_active } })}
                        className="text-xs text-gray-400 hover:text-white"
                      >
                        {sla.is_active ? "Desativar" : "Ativar"}
                      </button>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <div className="text-xs text-gray-500">Resposta</div>
                      <div className="text-brand-400 font-bold text-lg">
                        {sla.response_minutes < 60 ? `${sla.response_minutes}min` : `${sla.response_minutes / 60}h`}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">Resolução</div>
                      <div className="text-brand-400 font-bold text-lg">{sla.resolution_hours}h</div>
                    </div>
                    {sla.escalation_hours != null && (
                      <div>
                        <div className="text-xs text-gray-500">Escalação</div>
                        <div className="text-yellow-400 font-bold text-lg">{sla.escalation_hours}h</div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Tab 4: Relatório ──────────────────────────────────────────────────────────
function RelatorioTab() {
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<string>("");
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: assessments = [] } = useQuery({
    queryKey: ["ce-assessments"],
    queryFn: complianceEnterpriseApi.listAssessments,
  });

  const handleGenerate = async () => {
    if (!selectedAssessmentId) return;
    setLoading(true);
    setError(null);
    try {
      const r = await complianceEnterpriseApi.getAssessmentReport(selectedAssessmentId);
      setReport(r);
    } catch (e: unknown) {
      setError("Erro ao gerar relatório. Verifique se o assessment existe.");
    } finally {
      setLoading(false);
    }
  };

  const SEV_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

  return (
    <div className="space-y-6">
      {/* Selector */}
      <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
        <h3 className="text-white font-semibold mb-4">Gerar Relatório de Compliance</h3>
        <div className="flex gap-3">
          <select
            value={selectedAssessmentId}
            onChange={e => setSelectedAssessmentId(e.target.value)}
            className="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
          >
            <option value="">Selecione um assessment...</option>
            {assessments.map(a => (
              <option key={a.id} value={a.id}>
                {a.pack_name} — {a.name} ({a.status === "completed" ? "Concluído" : "Em andamento"})
              </option>
            ))}
          </select>
          <button
            onClick={handleGenerate}
            disabled={!selectedAssessmentId || loading}
            className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50 flex items-center gap-2"
          >
            <BarChart2 size={16} />
            {loading ? "Gerando..." : "Gerar Relatório"}
          </button>
        </div>
        {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
      </div>

      {/* Report Display */}
      {report && (
        <div className="space-y-4">
          {/* Score header */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
            <div className="flex items-center gap-6">
              <ScoreRing score={report.score} />
              <div className="flex-1">
                <h3 className="text-white font-bold text-lg">{report.pack_name}</h3>
                <p className="text-gray-400 text-sm mb-2">
                  Gerado em {new Date(report.generated_at).toLocaleString("pt-BR")} ·{" "}
                  <span className={`font-medium ${report.status === "completed" ? "text-green-400" : "text-yellow-400"}`}>
                    {report.status === "completed" ? "Avaliação concluída" : "Em andamento"}
                  </span>
                </p>
                <div className="flex gap-6 text-sm">
                  <span className="text-green-400 font-medium">{report.compliant_count} conformes</span>
                  <span className="text-red-400 font-medium">{report.non_compliant_count} não conformes</span>
                  <span className="text-gray-400">{report.not_evaluated_count} não avaliados</span>
                  <span className="text-gray-400">{report.total_controls} total</span>
                </div>
              </div>
            </div>
          </div>

          {/* Breakdown by category */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
            <h4 className="text-white font-semibold mb-4">Score por Categoria</h4>
            <div className="space-y-3">
              {Object.entries(report.breakdown_by_category).map(([cat, counts]) => {
                const nonNA = counts.total - counts.not_applicable;
                const catScore = nonNA > 0 ? Math.round((counts.compliant / nonNA) * 100) : 0;
                return (
                  <div key={cat}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-gray-300">{cat}</span>
                      <div className="flex items-center gap-3 text-xs text-gray-400">
                        <span className="text-green-400">{counts.compliant} conf.</span>
                        <span className="text-red-400">{counts.non_compliant} n/c</span>
                        <span className="font-bold text-white">{catScore}%</span>
                      </div>
                    </div>
                    <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          catScore >= 75 ? "bg-green-500" : catScore >= 50 ? "bg-yellow-500" : "bg-red-500"
                        }`}
                        style={{ width: `${catScore}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Gaps */}
          {report.gaps.length > 0 && (
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
              <h4 className="text-white font-semibold mb-4">
                Gaps Críticos / Altos ({report.gaps.length} controles)
              </h4>
              <div className="space-y-2">
                {report.gaps
                  .sort((a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9))
                  .map(gap => (
                    <div key={gap.control_id} className="flex items-start gap-3 p-3 bg-gray-750 rounded-lg border border-gray-600">
                      <XCircle size={16} className="text-red-400 mt-0.5 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-0.5">
                          <span className="text-xs font-mono text-gray-400">{gap.control_id}</span>
                          <span className={`text-xs px-1.5 py-0.5 rounded border ${SEV_COLORS[gap.severity] ?? SEV_COLORS.medium}`}>
                            {gap.severity}
                          </span>
                          <span className="text-xs text-gray-500">{gap.category}</span>
                        </div>
                        <div className="text-white text-sm">{gap.title}</div>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Recommendations */}
          {report.recommendations.length > 0 && (
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
              <h4 className="text-white font-semibold mb-4">Recomendações Prioritárias</h4>
              <div className="space-y-3">
                {report.recommendations.map(rec => (
                  <div key={rec.control_id} className="flex items-start gap-3 p-3 bg-gray-750 rounded-lg border border-gray-600">
                    <span className="bg-brand-600 text-white text-xs font-bold w-6 h-6 rounded-full flex items-center justify-center shrink-0">
                      {rec.priority}
                    </span>
                    <div>
                      <div className="text-white text-sm font-medium">{rec.title}</div>
                      <div className="text-xs text-gray-400 mt-0.5">
                        {rec.category} · <span className={`${rec.severity === "critical" ? "text-red-400" : "text-orange-400"}`}>{rec.severity}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.gaps.length === 0 && (
            <div className="flex items-center gap-3 p-4 bg-green-900/20 border border-green-700 rounded-xl">
              <CheckCircle size={20} className="text-green-400" />
              <p className="text-green-300 text-sm font-medium">
                Nenhum gap crítico ou alto encontrado. Excelente conformidade!
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function ComplianceEnterprisePage() {
  const [tab, setTab] = useState<Tab>("packs");

  const TABS: { id: Tab; label: string; icon: JSX.Element }[] = [
    { id: "packs", label: "Compliance Packs", icon: <Shield size={16} /> },
    { id: "bcdr", label: "BC/DR", icon: <Activity size={16} /> },
    { id: "sla", label: "SLA", icon: <FileCheck2 size={16} /> },
    { id: "relatorio", label: "Relatório", icon: <BarChart2 size={16} /> },
  ];

  return (
    <main className="flex-1 overflow-auto bg-gray-950 p-6">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-1">Compliance Enterprise</h1>
        <p className="text-gray-400 text-sm mb-6">
          Packs CIS · PCI-DSS · BACEN 4.658 · LGPD | Planos BC/DR | SLA | Relatórios de conformidade
        </p>

        <div className="flex gap-1 mb-6 bg-gray-800 rounded-xl p-1 border border-gray-700">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors flex-1 justify-center ${
                tab === t.id
                  ? "bg-brand-600 text-white"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>

        {tab === "packs" && <PacksTab />}
        {tab === "bcdr" && <BcdrTab />}
        {tab === "sla" && <SlaTab />}
        {tab === "relatorio" && <RelatorioTab />}
      </div>
    </main>
  );
}
