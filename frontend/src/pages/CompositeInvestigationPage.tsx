import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Flame, Network, Server, Monitor, Plus, Loader2,
  CheckCircle2, Clock, AlertTriangle, ArrowRight,
  Sparkles, ChevronDown, ChevronRight, Trash2, Users,
  Send, RefreshCw, ClipboardList, Wrench, MessageSquare,
  RotateCcw, Layers,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import {
  compositeApi,
  type CompositeDomain,
  type CompositeInvestigation,
  type SubInvestigation,
} from "../api/composite";
import { useAuthStore } from "../store/authStore";
import toast from "react-hot-toast";

// ── Config de domínio ─────────────────────────────────────────────────────────

const DOMAIN_CFG: Record<CompositeDomain, { label: string; icon: typeof Flame; color: string; agentRoute: string }> = {
  firewall: { label: "Firewall",   icon: Flame,   color: "text-orange-600 bg-orange-50 border-orange-200", agentRoute: "/agent" },
  network:  { label: "Redes",      icon: Network,  color: "text-blue-600 bg-blue-50 border-blue-200",       agentRoute: "/network-agent" },
  n3:       { label: "Servidores", icon: Server,   color: "text-purple-600 bg-purple-50 border-purple-200", agentRoute: "/server-analysis" },
  rmm:      { label: "Estações",   icon: Monitor,  color: "text-green-600 bg-green-50 border-green-200",    agentRoute: "/rmm-agent" },
};

const STATUS_LABELS: Record<SubInvestigation["status"], { label: string; icon: typeof Clock; className: string }> = {
  pending:     { label: "Pendente",       icon: Clock,         className: "bg-gray-100 text-gray-500" },
  assigned:    { label: "Atribuído",      icon: Users,         className: "bg-blue-100 text-blue-600" },
  in_progress: { label: "Em andamento",   icon: RefreshCw,     className: "bg-brand-100 text-brand-700" },
  submitted:   { label: "Enviado",        icon: CheckCircle2,  className: "bg-green-100 text-green-700" },
  escalated:   { label: "Escalado",       icon: AlertTriangle, className: "bg-amber-100 text-amber-700" },
};

// ── SubInvestigation row ──────────────────────────────────────────────────────

function SubRow({
  sub,
  compositeId,
  compositeSymptom,
}: {
  sub: SubInvestigation;
  compositeId: string;
  compositeSymptom: string;
}) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);

  const cfg = DOMAIN_CFG[sub.domain];
  const statusCfg = STATUS_LABELS[sub.status];
  const Icon = cfg.icon;
  const StatusIcon = statusCfg.icon;

  const reopenMut = useMutation({
    mutationFn: () => compositeApi.reopen(compositeId, sub.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["composite", compositeId] }),
    onError: () => toast.error("Erro ao reabrir sub-investigação."),
  });

  return (
    <div className={`border rounded-xl overflow-hidden ${cfg.color}`}>
      <div className="flex items-center gap-3 px-4 py-3">
        <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 border ${cfg.color}`}>
          <Icon size={13} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-800">{cfg.label}</p>
          {sub.assigned_to_name && (
            <p className="text-xs text-gray-500">{sub.assigned_to_name}</p>
          )}
          {sub.submitted_at && (
            <p className="text-xs text-gray-400">
              Enviado {new Date(sub.submitted_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full font-medium ${statusCfg.className}`}>
            <StatusIcon size={10} />
            {statusCfg.label}
          </span>
          {sub.findings && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-gray-400 hover:text-gray-700"
            >
              {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            </button>
          )}
          {/* Reopen submitted sub */}
          {sub.status === "submitted" && (
            <button
              onClick={() => reopenMut.mutate()}
              disabled={reopenMut.isPending}
              title="Reabrir para complementar"
              className="text-gray-400 hover:text-amber-600 transition-colors"
            >
              {reopenMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
            </button>
          )}
          {/* Navigate to agent with investigation context */}
          <button
            onClick={() => navigate(cfg.agentRoute, {
              state: {
                context: compositeSymptom,
                suggested_query: compositeSymptom,
                compositeId: sub.composite_id,
                subInvestigationId: sub.id,
              },
            })}
            title="Abrir agente"
            className="text-gray-400 hover:text-brand-600 transition-colors"
          >
            <ArrowRight size={14} />
          </button>
        </div>
      </div>
      {expanded && sub.findings && (
        <div className="px-4 pb-4 border-t border-current/20 pt-3">
          <p className="text-xs font-medium text-gray-500 mb-1">Conclusão do especialista</p>
          <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{sub.findings}</p>
        </div>
      )}
    </div>
  );
}

// ── Composite detail ──────────────────────────────────────────────────────────

function CompositeDetail({ inv, onBack }: { inv: CompositeInvestigation; onBack: () => void }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [chatMsg, setChatMsg] = useState("");
  const [chatResponse, setChatResponse] = useState<string | null>(null);
  const [chatLoading, setChatLoading] = useState(false);

  const consolidateMut = useMutation({
    mutationFn: () => compositeApi.consolidate(inv.id),
    onSuccess: (updated) => qc.setQueryData(["composite", inv.id], updated),
    onError: () => toast.error("Erro ao consolidar."),
  });

  const actionPlanMut = useMutation({
    mutationFn: () => compositeApi.generateActionPlan(inv.id),
    onSuccess: (updated) => {
      qc.setQueryData(["composite", inv.id], updated);
      if (updated.action_plan_session_id) {
        navigate(`/assistant?session=${updated.action_plan_session_id}`);
      }
    },
    onError: () => toast.error("Erro ao gerar plano de ação."),
  });

  const resolveMut = useMutation({
    mutationFn: () => compositeApi.resolve(inv.id),
    onSuccess: (updated) => { qc.setQueryData(["composite", inv.id], updated); onBack(); },
    onError: () => toast.error("Erro ao resolver investigação."),
  });

  const handleChat = async () => {
    if (!chatMsg.trim()) return;
    setChatLoading(true);
    try {
      const res = await compositeApi.chat(inv.id, chatMsg.trim());
      setChatResponse(res.response);
      setChatMsg("");
    } catch {
      toast.error("Erro ao enviar mensagem.");
    } finally {
      setChatLoading(false);
    }
  };

  const submitted = inv.sub_investigations.filter((s) => s.status === "submitted" || s.findings).length;
  const total = inv.sub_investigations.length;
  const hasAnyFindings = inv.sub_investigations.some((s) => s.findings);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start gap-3 justify-between">
        <div>
          <button onClick={onBack} className="text-xs text-gray-400 hover:text-gray-600 mb-1">← Voltar</button>
          <p className="text-base font-semibold text-gray-900">{inv.symptom}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            Aberta por {inv.created_by_name} ·{" "}
            {new Date(inv.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
          </p>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${
          inv.status === "resolved"      ? "bg-green-100 text-green-700" :
          inv.status === "consolidating" ? "bg-violet-100 text-violet-700" :
          inv.status === "active"        ? "bg-brand-100 text-brand-700" :
                                           "bg-gray-100 text-gray-600"
        }`}>
          {inv.status === "resolved"      ? "Resolvida" :
           inv.status === "consolidating" ? "Consolidando" :
           inv.status === "active"        ? "Em andamento" : "Rascunho"}
        </span>
      </div>

      {/* Progress */}
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-3 flex items-center gap-3">
        <div className="flex-1">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Progresso dos domínios</span>
            <span className="font-medium">{submitted}/{total} com achados</span>
          </div>
          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 rounded-full transition-all"
              style={{ width: total > 0 ? `${(submitted / total) * 100}%` : "0%" }}
            />
          </div>
        </div>
      </div>

      {/* Sub-investigations */}
      <div className="space-y-2">
        {inv.sub_investigations.map((sub) => (
          <SubRow key={sub.id} sub={sub} compositeId={inv.id} compositeSymptom={inv.symptom} />
        ))}
      </div>

      {/* Consolidação */}
      {inv.consolidation && (
        <div className="border border-violet-200 bg-violet-50 rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-violet-600" />
            <p className="text-xs font-semibold text-violet-700">Consolidação — Causa raiz identificada</p>
          </div>
          <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{inv.consolidation}</p>
        </div>
      )}

      {/* N3 Chat */}
      <div className="border border-gray-200 rounded-xl p-3 space-y-2">
        <p className="text-xs font-semibold text-gray-600 flex items-center gap-1.5">
          <MessageSquare size={12} /> Chat N3 — consulta contextualizada
        </p>
        {chatResponse && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-2.5">
            <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">{chatResponse}</p>
          </div>
        )}
        <div className="flex gap-2">
          <input
            value={chatMsg}
            onChange={(e) => setChatMsg(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleChat(); } }}
            placeholder="Pergunte algo sobre a investigação…"
            className="flex-1 border border-gray-300 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <button
            onClick={handleChat}
            disabled={!chatMsg.trim() || chatLoading}
            className="flex items-center gap-1 px-3 py-1.5 bg-brand-600 text-white text-xs rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {chatLoading ? <Loader2 size={11} className="animate-spin" /> : <Send size={11} />}
          </button>
        </div>
      </div>

      {/* Ações N3 */}
      <div className="space-y-2 pt-1">
        {/* Consolidar — always show when there are any findings */}
        {hasAnyFindings && inv.status !== "resolved" && (
          <button
            onClick={() => consolidateMut.mutate()}
            disabled={consolidateMut.isPending}
            className="w-full flex items-center justify-center gap-2 py-2.5 bg-violet-600 text-white text-sm font-medium rounded-xl hover:bg-violet-700 disabled:opacity-50"
          >
            {consolidateMut.isPending
              ? <><Loader2 size={13} className="animate-spin" /> Consolidando…</>
              : inv.consolidation
              ? <><RefreshCw size={13} /> Re-consolidar com achados atualizados</>
              : <><Sparkles size={13} /> Consolidar e identificar causa raiz</>}
          </button>
        )}

        {inv.consolidation && (
          <>
            <button
              onClick={() => actionPlanMut.mutate()}
              disabled={actionPlanMut.isPending}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-xl hover:bg-brand-700 disabled:opacity-50"
            >
              {actionPlanMut.isPending
                ? <><Loader2 size={13} className="animate-spin" /> Gerando…</>
                : <><ClipboardList size={13} /> Gerar Plano de Ação no Assistente IA</>}
            </button>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => navigate("/remediation", {
                  state: { prefill: inv.consolidation, source: "composite", compositeId: inv.id },
                })}
                className="flex items-center justify-center gap-2 py-2 border border-amber-300 text-amber-700 text-sm font-medium rounded-xl hover:bg-amber-50"
              >
                <Wrench size={13} /> Criar Remediação
              </button>
              <button
                onClick={() => navigate("/glpi", {
                  state: { prefill: `Investigação Composta — ${inv.symptom}\n\n${inv.consolidation}` },
                })}
                className="flex items-center justify-center gap-2 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-xl hover:bg-gray-50"
              >
                <MessageSquare size={13} /> Criar Ticket IA
              </button>
            </div>
          </>
        )}

        {inv.status !== "resolved" && inv.consolidation && (
          <button
            onClick={() => { if (confirm("Marcar como resolvida?")) resolveMut.mutate(); }}
            disabled={resolveMut.isPending}
            className="w-full flex items-center justify-center gap-2 py-2 border border-green-300 text-green-700 text-sm font-medium rounded-xl hover:bg-green-50 disabled:opacity-50"
          >
            <CheckCircle2 size={13} /> Marcar como resolvida
          </button>
        )}
      </div>
    </div>
  );
}

// ── Create modal ──────────────────────────────────────────────────────────────

function CreateModal({
  onClose,
  onCreate,
  initialSymptom = "",
  fromCrossDomain = false,
}: {
  onClose: () => void;
  onCreate: (inv: CompositeInvestigation) => void;
  initialSymptom?: string;
  fromCrossDomain?: boolean;
}) {
  const [symptom, setSymptom] = useState(initialSymptom);
  const [domains, setDomains] = useState<Set<CompositeDomain>>(new Set(["firewall", "network", "n3", "rmm"]));

  const toggle = (d: CompositeDomain) =>
    setDomains((prev) => { const n = new Set(prev); n.has(d) ? n.delete(d) : n.add(d); return n; });

  const createMut = useMutation({
    mutationFn: () => compositeApi.create({ symptom: symptom.trim(), domains: Array.from(domains) }),
    onSuccess: onCreate,
    onError: () => toast.error("Erro ao criar investigação."),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-2xl shadow-2xl w-[480px] p-6 space-y-4">
        <h3 className="text-sm font-semibold text-gray-800">Nova Investigação Composta</h3>

        {fromCrossDomain && (
          <div className="flex items-start gap-2 bg-violet-50 border border-violet-200 rounded-xl px-3 py-2.5">
            <Layers size={12} className="text-violet-500 shrink-0 mt-0.5" />
            <p className="text-xs text-violet-700">Escalado de Investigação Cruzada — problema pré-preenchido.</p>
          </div>
        )}

        <div>
          <label className="text-xs font-medium text-gray-600">Sintoma / problema</label>
          <textarea
            autoFocus
            value={symptom}
            onChange={(e) => setSymptom(e.target.value)}
            rows={3}
            placeholder="Descreva o sintoma observado…"
            className="mt-1 w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
          />
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600">Domínios a investigar</label>
          <div className="mt-1.5 grid grid-cols-2 gap-2">
            {(["firewall", "network", "n3", "rmm"] as CompositeDomain[]).map((d) => {
              const cfg = DOMAIN_CFG[d];
              const Icon = cfg.icon;
              const sel = domains.has(d);
              return (
                <button
                  key={d}
                  onClick={() => toggle(d)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-sm transition-colors ${
                    sel ? `${cfg.color} font-medium` : "border-gray-200 text-gray-500 hover:bg-gray-50"
                  }`}
                >
                  <Icon size={13} className="shrink-0" />
                  {cfg.label}
                  {sel && <CheckCircle2 size={12} className="ml-auto shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex gap-2 pt-1">
          <button onClick={onClose} className="flex-1 text-xs border border-gray-200 rounded-xl py-2.5 text-gray-600 hover:bg-gray-50">
            Cancelar
          </button>
          <button
            onClick={() => createMut.mutate()}
            disabled={!symptom.trim() || domains.size === 0 || createMut.isPending}
            className="flex-1 flex items-center justify-center gap-1.5 text-xs bg-brand-600 text-white rounded-xl py-2.5 hover:bg-brand-700 disabled:opacity-50"
          >
            {createMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
            {createMut.isPending ? "Criando…" : "Criar e notificar especialistas"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Composite list item ───────────────────────────────────────────────────────

function CompositeListItem({ inv, onSelect }: { inv: CompositeInvestigation; onSelect: () => void }) {
  const qc = useQueryClient();
  const submitted = inv.sub_investigations.filter((s) => s.status === "submitted" || s.findings).length;
  const total = inv.sub_investigations.length;

  const deleteMut = useMutation({
    mutationFn: () => compositeApi.delete(inv.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["composite-list"] }),
  });

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden hover:border-brand-300 transition-colors">
      <div className="flex items-start gap-3 p-4 cursor-pointer" onClick={onSelect}>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-800 truncate">{inv.symptom}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {new Date(inv.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })} ·{" "}
            {inv.created_by_name}
          </p>
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {inv.domains.map((d) => {
              const cfg = DOMAIN_CFG[d];
              const Icon = cfg.icon;
              const sub = inv.sub_investigations.find((s) => s.domain === d);
              const statusCfg = sub ? STATUS_LABELS[sub.status] : STATUS_LABELS.pending;
              return (
                <span key={d} className={`flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${cfg.color}`}>
                  <Icon size={9} /> {cfg.label}
                  <span className={`ml-1 px-1 rounded-full ${statusCfg.className}`}>{statusCfg.label}</span>
                </span>
              );
            })}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-gray-400">{submitted}/{total}</span>
          <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
            inv.status === "resolved"      ? "bg-green-100 text-green-700" :
            inv.status === "consolidating" ? "bg-violet-100 text-violet-700" :
            inv.status === "active"        ? "bg-brand-100 text-brand-700" :
                                             "bg-gray-100 text-gray-600"
          }`}>
            {inv.status === "resolved" ? "Resolvida" : inv.status === "consolidating" ? "Consolidando" :
             inv.status === "active" ? "Ativa" : "Rascunho"}
          </span>
          <button
            onClick={(e) => { e.stopPropagation(); if (confirm("Remover?")) deleteMut.mutate(); }}
            className="text-gray-300 hover:text-red-500 transition-colors"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function CompositeInvestigationPage() {
  const qc = useQueryClient();
  const location = useLocation();
  const tenantRole = useAuthStore((s) => s.tenantRole);
  const isN3OrAdmin = tenantRole === "admin" || tenantRole === "analyst_n2";

  const escalation = location.state as {
    symptom?: string;
    correlation?: string;
    fromCrossDomain?: boolean;
    crossDomainSessionId?: string;
  } | null;

  const [showCreate, setShowCreate] = useState(!!escalation?.fromCrossDomain && isN3OrAdmin);
  const [activeId, setActiveId] = useState<string | null>(null);

  const { data: list = [], isLoading } = useQuery({
    queryKey: ["composite-list"],
    queryFn: compositeApi.list,
  });

  const { data: activeInv } = useQuery({
    queryKey: ["composite", activeId],
    queryFn: () => compositeApi.get(activeId!),
    enabled: !!activeId,
    refetchInterval: (query) => {
      const data = (query as { state?: { data?: CompositeInvestigation } }).state?.data;
      if (!data) return false;
      return data.status === "active" || data.status === "consolidating" ? 3000 : false;
    },
  });

  const handleCreated = (inv: CompositeInvestigation) => {
    qc.setQueryData(["composite", inv.id], inv);
    qc.invalidateQueries({ queryKey: ["composite-list"] });
    setShowCreate(false);
    setActiveId(inv.id);
  };

  if (activeId && activeInv) {
    return (
      <PageWrapper title="Investigação Composta">
        <div className="max-w-2xl mx-auto">
          <CompositeDetail inv={activeInv} onBack={() => setActiveId(null)} />
        </div>
        {showCreate && <CreateModal onClose={() => setShowCreate(false)} onCreate={handleCreated} />}
      </PageWrapper>
    );
  }

  return (
    <PageWrapper
      title="Investigação Composta"
      subtitle="Coordene especialistas de múltiplos domínios em uma investigação unificada"
    >
      <div className="max-w-2xl mx-auto space-y-4">
        {isN3OrAdmin && (
          <div className="flex justify-end">
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 text-sm px-4 py-2 bg-brand-600 text-white rounded-xl hover:bg-brand-700"
            >
              <Plus size={14} /> Nova investigação composta
            </button>
          </div>
        )}

        {isLoading && (
          <div className="flex items-center justify-center h-32 gap-2 text-gray-400 text-sm">
            <Loader2 size={15} className="animate-spin" /> Carregando…
          </div>
        )}
        {!isLoading && list.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <Users size={32} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">Nenhuma investigação composta ainda.</p>
            {isN3OrAdmin && (
              <p className="text-xs mt-1">Crie uma para coordenar especialistas de múltiplos domínios.</p>
            )}
          </div>
        )}
        {list.map((inv) => (
          <CompositeListItem key={inv.id} inv={inv} onSelect={() => setActiveId(inv.id)} />
        ))}
      </div>

      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreate={handleCreated}
          initialSymptom={escalation?.symptom ?? ""}
          fromCrossDomain={!!escalation?.fromCrossDomain}
        />
      )}
    </PageWrapper>
  );
}
