import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Flame, Network, Server, Monitor, Play, Loader2,
  CheckCircle2, AlertTriangle, Clock, RefreshCw, Sparkles, ArrowRight,
  ChevronDown, ChevronRight, History, Trash2, Wrench, MessageSquare,
  RotateCcw, Send, Plus, Users, GitMerge, ClipboardList, Zap,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import {
  crossDomainApi,
  type CrossDomainAgentType,
  type CrossDomainSession,
  type CrossDomainSubResult,
} from "../api/crossDomain";
import {
  compositeApi,
  type CompositeDomain,
  type CompositeInvestigation,
  type SubInvestigation,
} from "../api/composite";
import { permissionsApi } from "../api/permissions";
import { useAuthStore } from "../store/authStore";
import toast from "react-hot-toast";

// ── Shared domain config ──────────────────────────────────────────────────────

const DOMAIN_CONFIG: Record<CrossDomainAgentType, {
  label: string; icon: typeof Flame; color: string; route: string;
}> = {
  firewall: { label: "Firewall",   icon: Flame,   color: "text-orange-600 bg-orange-50 border-orange-200", route: "/agent" },
  network:  { label: "Redes",      icon: Network,  color: "text-blue-600 bg-blue-50 border-blue-200",       route: "/network-agent" },
  n3:       { label: "Servidores", icon: Server,   color: "text-purple-600 bg-purple-50 border-purple-200", route: "/server-analysis" },
  rmm:      { label: "Estações",   icon: Monitor,  color: "text-green-600 bg-green-50 border-green-200",    route: "/rmm-agent" },
};

const STATUS_LABELS: Record<SubInvestigation["status"], { label: string; icon: typeof Clock; className: string }> = {
  pending:     { label: "Pendente",     icon: Clock,         className: "bg-gray-100 text-gray-500" },
  assigned:    { label: "Atribuído",    icon: Users,         className: "bg-blue-100 text-blue-600" },
  in_progress: { label: "Em andamento", icon: RefreshCw,     className: "bg-brand-100 text-brand-700" },
  submitted:   { label: "Enviado",      icon: CheckCircle2,  className: "bg-green-100 text-green-700" },
  escalated:   { label: "Escalado",     icon: AlertTriangle, className: "bg-amber-100 text-amber-700" },
};

// ── CrossDomain sub-result card ───────────────────────────────────────────────

function SubResultCard({
  sub, sessionId, onNavigate, onRerun,
}: {
  sub: CrossDomainSubResult;
  sessionId: string;
  onNavigate: () => void;
  onRerun: (domain: CrossDomainAgentType, additionalContext?: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [showRerun, setShowRerun] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [rerunCtx, setRerunCtx] = useState("");
  const [chatMsg, setChatMsg] = useState("");
  const [chatResponse, setChatResponse] = useState<string | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const cfg = DOMAIN_CONFIG[sub.domain];
  const Icon = cfg.icon;

  const handleChat = async () => {
    if (!chatMsg.trim()) return;
    setChatLoading(true);
    try {
      const res = await crossDomainApi.chat(sessionId, sub.domain, chatMsg.trim());
      setChatResponse(res.response);
      setChatMsg("");
    } catch {
      toast.error("Erro ao enviar mensagem.");
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className={`border rounded-xl overflow-hidden ${cfg.color}`}>
      <div className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none" onClick={() => sub.synthesis && setExpanded((v) => !v)}>
        <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 border ${cfg.color}`}><Icon size={13} /></div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-800">{cfg.label}</p>
          {sub.status === "done"    && sub.synthesis && <p className="text-xs text-gray-600 truncate">{sub.synthesis.slice(0, 80)}…</p>}
          {sub.status === "running" && <p className="text-xs text-gray-500">Investigando…</p>}
          {sub.status === "pending" && <p className="text-xs text-gray-400">Aguardando…</p>}
          {sub.status === "error"   && <p className="text-xs text-red-500">{sub.error ?? "Erro na investigação"}</p>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {sub.status === "running" && <Loader2 size={14} className="animate-spin text-gray-500" />}
          {sub.status === "done"    && <CheckCircle2 size={14} className="text-green-600" />}
          {sub.status === "error"   && <AlertTriangle size={14} className="text-red-500" />}
          {sub.status === "pending" && <Clock size={14} className="text-gray-400" />}
          {sub.investigation_session_id && (
            <button onClick={(e) => { e.stopPropagation(); onNavigate(); }} className="text-[11px] px-2 py-0.5 rounded border border-current opacity-70 hover:opacity-100 transition-opacity">Abrir</button>
          )}
          {(sub.status === "done" || sub.status === "error") && (
            <button onClick={(e) => { e.stopPropagation(); setShowRerun((v) => !v); setShowChat(false); }} title="Re-executar" className="opacity-60 hover:opacity-100 transition-opacity"><RotateCcw size={12} /></button>
          )}
          {sub.status === "done" && (
            <button onClick={(e) => { e.stopPropagation(); setShowChat((v) => !v); setShowRerun(false); }} title="Chat" className="opacity-60 hover:opacity-100 transition-opacity"><MessageSquare size={12} /></button>
          )}
          {sub.synthesis && (expanded ? <ChevronDown size={13} className="text-gray-400" /> : <ChevronRight size={13} className="text-gray-400" />)}
        </div>
      </div>

      {expanded && sub.synthesis && (
        <div className="px-4 pb-4 border-t border-current/20 pt-3">
          <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">{sub.synthesis}</p>
        </div>
      )}

      {showRerun && (
        <div className="px-4 pb-4 border-t border-current/20 pt-3 space-y-2" onClick={(e) => e.stopPropagation()}>
          <p className="text-xs font-semibold text-gray-700">Re-executar análise</p>
          <textarea
            value={rerunCtx}
            onChange={(e) => setRerunCtx(e.target.value)}
            rows={2}
            placeholder="Contexto adicional (opcional)"
            className="w-full border border-gray-300 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-violet-500 resize-none bg-white"
          />
          <div className="flex gap-2">
            <button onClick={() => { onRerun(sub.domain, rerunCtx.trim() || undefined); setShowRerun(false); setRerunCtx(""); }} className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-violet-600 text-white rounded-lg hover:bg-violet-700">
              <RotateCcw size={11} /> Re-executar
            </button>
            <button onClick={() => setShowRerun(false)} className="text-xs px-3 py-1.5 border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50">Cancelar</button>
          </div>
        </div>
      )}

      {showChat && (
        <div className="px-4 pb-4 border-t border-current/20 pt-3 space-y-2" onClick={(e) => e.stopPropagation()}>
          <p className="text-xs font-semibold text-gray-700">Chat com {cfg.label}</p>
          {chatResponse && (
            <div className="bg-white border border-gray-200 rounded-lg p-2.5">
              <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">{chatResponse}</p>
            </div>
          )}
          <div className="flex gap-2">
            <input
              value={chatMsg}
              onChange={(e) => setChatMsg(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleChat(); } }}
              placeholder={`Pergunte sobre ${cfg.label}…`}
              className="flex-1 border border-gray-300 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-violet-500 bg-white"
            />
            <button onClick={handleChat} disabled={!chatMsg.trim() || chatLoading} className="flex items-center gap-1 px-3 py-1.5 bg-violet-600 text-white text-xs rounded-lg hover:bg-violet-700 disabled:opacity-50">
              {chatLoading ? <Loader2 size={11} className="animate-spin" /> : <Send size={11} />}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── CrossDomain session detail ────────────────────────────────────────────────

function AutoSessionDetail({ sessionId, onBack }: { sessionId: string; onBack: () => void }) {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: session, isLoading } = useQuery({
    queryKey: ["cross-domain", sessionId],
    queryFn: () => crossDomainApi.get(sessionId),
    refetchInterval: (query) => {
      const data = (query as { state?: { data?: CrossDomainSession } }).state?.data;
      if (!data) return false;
      return data.status === "running" ? 2000 : false;
    },
  });

  const correlateMut = useMutation({
    mutationFn: () => crossDomainApi.correlate(sessionId),
    onSuccess: (s) => qc.setQueryData(["cross-domain", sessionId], s),
    onError: () => toast.error("Erro ao correlacionar."),
  });

  const rerunMut = useMutation({
    mutationFn: ({ domain, ctx }: { domain: CrossDomainAgentType; ctx?: string }) =>
      crossDomainApi.rerunDomain(sessionId, domain, ctx),
    onSuccess: (s) => { qc.setQueryData(["cross-domain", sessionId], s); toast.success("Re-análise iniciada."); },
    onError: () => toast.error("Erro ao re-executar."),
  });

  const deleteMut = useMutation({
    mutationFn: () => crossDomainApi.delete(sessionId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cross-domain-list"] }); onBack(); },
  });

  if (isLoading || !session) {
    return <div className="flex items-center justify-center h-64 gap-2 text-gray-500 text-sm"><Loader2 size={16} className="animate-spin" /> Carregando…</div>;
  }

  const anyDone = session.sub_results.some((s) => s.status === "done");

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <button onClick={onBack} className="text-xs text-gray-400 hover:text-gray-600 mb-1">← Voltar</button>
          <p className="text-sm font-semibold text-gray-800">{session.problem_description}</p>
          <p className="text-xs text-gray-400 mt-0.5">{new Date(session.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${session.status === "done" ? "bg-green-100 text-green-700" : session.status === "partial" ? "bg-amber-100 text-amber-700" : "bg-brand-100 text-brand-700"}`}>
            {session.status === "done" ? "Concluída" : session.status === "partial" ? "Parcial" : "Em andamento"}
          </span>
          <button onClick={() => { if (confirm("Remover investigação?")) deleteMut.mutate(); }} className="text-gray-400 hover:text-red-500 transition-colors"><Trash2 size={14} /></button>
        </div>
      </div>

      <div className="space-y-2">
        {session.sub_results.map((sub) => (
          <SubResultCard
            key={sub.domain}
            sub={sub}
            sessionId={sessionId}
            onNavigate={() => navigate(DOMAIN_CONFIG[sub.domain].route, { state: { context: session.problem_description } })}
            onRerun={(domain, ctx) => rerunMut.mutate({ domain, ctx })}
          />
        ))}
      </div>

      {anyDone && (
        <button onClick={() => correlateMut.mutate()} disabled={correlateMut.isPending} className="w-full flex items-center justify-center gap-2 py-2.5 bg-violet-600 text-white text-sm font-medium rounded-xl hover:bg-violet-700 disabled:opacity-50">
          {correlateMut.isPending
            ? <><Loader2 size={13} className="animate-spin" /> Correlacionando…</>
            : session.correlation
            ? <><RefreshCw size={13} /> Re-correlacionar domínios</>
            : <><Sparkles size={13} /> Correlacionar e identificar causa raiz</>}
        </button>
      )}

      {session.correlation && (
        <div className="border border-violet-200 bg-violet-50 rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2"><Sparkles size={14} className="text-violet-600" /><p className="text-xs font-semibold text-violet-700">Correlação IA — Causa raiz</p></div>
          <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{session.correlation}</p>
        </div>
      )}

      {session.correlation && (
        <div className="space-y-2">
          <button onClick={() => navigate("/assistant", { state: { prefill: session.correlation } })} className="w-full flex items-center justify-center gap-2 py-2.5 border border-brand-300 text-brand-700 text-sm font-medium rounded-xl hover:bg-brand-50">
            <ArrowRight size={13} /> Gerar Plano de Ação no Assistente IA
          </button>
          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => navigate("/remediation", { state: { prefill: session.correlation, source: "cross-domain", sessionId: session.id } })} className="flex items-center justify-center gap-2 py-2 border border-amber-300 text-amber-700 text-sm font-medium rounded-xl hover:bg-amber-50">
              <Wrench size={13} /> Criar Remediação
            </button>
            <button onClick={() => navigate("/glpi", { state: { prefill: `Investigação Cruzada — ${session.problem_description}\n\n${session.correlation}` } })} className="flex items-center justify-center gap-2 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-xl hover:bg-gray-50">
              <MessageSquare size={13} /> Criar Ticket IA
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Composite sub-row ─────────────────────────────────────────────────────────

function SubRow({ sub, compositeId, compositeSymptom }: { sub: SubInvestigation; compositeId: string; compositeSymptom: string }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const cfg = DOMAIN_CONFIG[sub.domain];
  const statusCfg = STATUS_LABELS[sub.status];
  const Icon = cfg.icon;
  const StatusIcon = statusCfg.icon;

  const reopenMut = useMutation({
    mutationFn: () => compositeApi.reopen(compositeId, sub.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["composite", compositeId] }),
    onError: () => toast.error("Erro ao reabrir."),
  });

  return (
    <div className={`border rounded-xl overflow-hidden ${cfg.color}`}>
      <div className="flex items-center gap-3 px-4 py-3">
        <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 border ${cfg.color}`}><Icon size={13} /></div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-800">{cfg.label}</p>
          {sub.assigned_to_name && <p className="text-xs text-gray-500">{sub.assigned_to_name}</p>}
          {sub.submitted_at && <p className="text-xs text-gray-400">Enviado {new Date(sub.submitted_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</p>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full font-medium ${statusCfg.className}`}>
            <StatusIcon size={10} />{statusCfg.label}
          </span>
          {sub.findings && (
            <button onClick={() => setExpanded((v) => !v)} className="text-gray-400 hover:text-gray-700">
              {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            </button>
          )}
          {sub.status === "submitted" && (
            <button onClick={() => reopenMut.mutate()} disabled={reopenMut.isPending} title="Reabrir" className="text-gray-400 hover:text-amber-600 transition-colors">
              {reopenMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
            </button>
          )}
          <button
            onClick={() => navigate(cfg.route, { state: { context: compositeSymptom, suggested_query: compositeSymptom, compositeId: sub.composite_id, subInvestigationId: sub.id } })}
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

// ── Composite investigation detail ────────────────────────────────────────────

function CoordDetail({ inv, onBack }: { inv: CompositeInvestigation; onBack: () => void }) {
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
      if (updated.action_plan_session_id) navigate(`/assistant?session=${updated.action_plan_session_id}`);
    },
    onError: () => toast.error("Erro ao gerar plano de ação."),
  });

  const resolveMut = useMutation({
    mutationFn: () => compositeApi.resolve(inv.id),
    onSuccess: (updated) => { qc.setQueryData(["composite", inv.id], updated); onBack(); },
    onError: () => toast.error("Erro ao resolver."),
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
      <div className="flex items-start gap-3 justify-between">
        <div>
          <button onClick={onBack} className="text-xs text-gray-400 hover:text-gray-600 mb-1">← Voltar</button>
          <p className="text-base font-semibold text-gray-900">{inv.symptom}</p>
          <p className="text-xs text-gray-400 mt-0.5">Aberta por {inv.created_by_name} · {new Date(inv.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</p>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${inv.status === "resolved" ? "bg-green-100 text-green-700" : inv.status === "consolidating" ? "bg-violet-100 text-violet-700" : inv.status === "active" ? "bg-brand-100 text-brand-700" : "bg-gray-100 text-gray-600"}`}>
          {inv.status === "resolved" ? "Resolvida" : inv.status === "consolidating" ? "Consolidando" : inv.status === "active" ? "Em andamento" : "Rascunho"}
        </span>
      </div>

      <div className="bg-gray-50 border border-gray-200 rounded-xl p-3">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Progresso dos domínios</span>
          <span className="font-medium">{submitted}/{total} com achados</span>
        </div>
        <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <div className="h-full bg-green-500 rounded-full transition-all" style={{ width: total > 0 ? `${(submitted / total) * 100}%` : "0%" }} />
        </div>
      </div>

      <div className="space-y-2">
        {inv.sub_investigations.map((sub) => (
          <SubRow key={sub.id} sub={sub} compositeId={inv.id} compositeSymptom={inv.symptom} />
        ))}
      </div>

      {inv.consolidation && (
        <div className="border border-violet-200 bg-violet-50 rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2"><Sparkles size={14} className="text-violet-600" /><p className="text-xs font-semibold text-violet-700">Consolidação — Causa raiz identificada</p></div>
          <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{inv.consolidation}</p>
        </div>
      )}

      <div className="border border-gray-200 rounded-xl p-3 space-y-2">
        <p className="text-xs font-semibold text-gray-600 flex items-center gap-1.5"><MessageSquare size={12} /> Chat N3 — consulta contextualizada</p>
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
          <button onClick={handleChat} disabled={!chatMsg.trim() || chatLoading} className="flex items-center gap-1 px-3 py-1.5 bg-brand-600 text-white text-xs rounded-lg hover:bg-brand-700 disabled:opacity-50">
            {chatLoading ? <Loader2 size={11} className="animate-spin" /> : <Send size={11} />}
          </button>
        </div>
      </div>

      <div className="space-y-2 pt-1">
        {hasAnyFindings && inv.status !== "resolved" && (
          <button onClick={() => consolidateMut.mutate()} disabled={consolidateMut.isPending} className="w-full flex items-center justify-center gap-2 py-2.5 bg-violet-600 text-white text-sm font-medium rounded-xl hover:bg-violet-700 disabled:opacity-50">
            {consolidateMut.isPending
              ? <><Loader2 size={13} className="animate-spin" /> Consolidando…</>
              : inv.consolidation
              ? <><RefreshCw size={13} /> Re-consolidar com achados atualizados</>
              : <><Sparkles size={13} /> Consolidar e identificar causa raiz</>}
          </button>
        )}
        {inv.consolidation && (
          <>
            <button onClick={() => actionPlanMut.mutate()} disabled={actionPlanMut.isPending} className="w-full flex items-center justify-center gap-2 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-xl hover:bg-brand-700 disabled:opacity-50">
              {actionPlanMut.isPending ? <><Loader2 size={13} className="animate-spin" /> Gerando…</> : <><ClipboardList size={13} /> Gerar Plano de Ação no Assistente IA</>}
            </button>
            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => navigate("/remediation", { state: { prefill: inv.consolidation, source: "composite", compositeId: inv.id } })} className="flex items-center justify-center gap-2 py-2 border border-amber-300 text-amber-700 text-sm font-medium rounded-xl hover:bg-amber-50">
                <Wrench size={13} /> Criar Remediação
              </button>
              <button onClick={() => navigate("/glpi", { state: { prefill: `Investigação Composta — ${inv.symptom}\n\n${inv.consolidation}` } })} className="flex items-center justify-center gap-2 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-xl hover:bg-gray-50">
                <MessageSquare size={13} /> Criar Ticket IA
              </button>
            </div>
          </>
        )}
        {inv.status !== "resolved" && inv.consolidation && (
          <button onClick={() => { if (confirm("Marcar como resolvida?")) resolveMut.mutate(); }} disabled={resolveMut.isPending} className="w-full flex items-center justify-center gap-2 py-2 border border-green-300 text-green-700 text-sm font-medium rounded-xl hover:bg-green-50 disabled:opacity-50">
            <CheckCircle2 size={13} /> Marcar como resolvida
          </button>
        )}
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
          <p className="text-xs text-gray-400 mt-0.5">{new Date(inv.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })} · {inv.created_by_name}</p>
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {inv.domains.map((d) => {
              const cfg = DOMAIN_CONFIG[d];
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
          <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${inv.status === "resolved" ? "bg-green-100 text-green-700" : inv.status === "consolidating" ? "bg-violet-100 text-violet-700" : inv.status === "active" ? "bg-brand-100 text-brand-700" : "bg-gray-100 text-gray-600"}`}>
            {inv.status === "resolved" ? "Resolvida" : inv.status === "consolidating" ? "Consolidando" : inv.status === "active" ? "Ativa" : "Rascunho"}
          </span>
          <button onClick={(e) => { e.stopPropagation(); if (confirm("Remover?")) deleteMut.mutate(); }} className="text-gray-300 hover:text-red-500 transition-colors"><Trash2 size={13} /></button>
        </div>
      </div>
    </div>
  );
}

// ── Create Composite modal ────────────────────────────────────────────────────

function CreateCompositeModal({ onClose, onCreate }: { onClose: () => void; onCreate: (inv: CompositeInvestigation) => void }) {
  const [symptom, setSymptom] = useState("");
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
        <h3 className="text-sm font-semibold text-gray-800">Nova Investigação Coordenada</h3>
        <div>
          <label className="text-xs font-medium text-gray-600">Sintoma / problema</label>
          <textarea autoFocus value={symptom} onChange={(e) => setSymptom(e.target.value)} rows={3} placeholder="Descreva o sintoma observado…" className="mt-1 w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-600">Domínios a investigar</label>
          <div className="mt-1.5 grid grid-cols-2 gap-2">
            {(["firewall", "network", "n3", "rmm"] as CompositeDomain[]).map((d) => {
              const cfg = DOMAIN_CONFIG[d];
              const Icon = cfg.icon;
              const sel = domains.has(d);
              return (
                <button key={d} onClick={() => toggle(d)} className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-sm transition-colors ${sel ? `${cfg.color} font-medium` : "border-gray-200 text-gray-500 hover:bg-gray-50"}`}>
                  <Icon size={13} className="shrink-0" />{cfg.label}{sel && <CheckCircle2 size={12} className="ml-auto shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>
        <div className="flex gap-2 pt-1">
          <button onClick={onClose} className="flex-1 text-xs border border-gray-200 rounded-xl py-2.5 text-gray-600 hover:bg-gray-50">Cancelar</button>
          <button onClick={() => createMut.mutate()} disabled={!symptom.trim() || domains.size === 0 || createMut.isPending} className="flex-1 flex items-center justify-center gap-1.5 text-xs bg-brand-600 text-white rounded-xl py-2.5 hover:bg-brand-700 disabled:opacity-50">
            {createMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
            {createMut.isPending ? "Criando…" : "Criar e notificar especialistas"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Mode selection modal ──────────────────────────────────────────────────────

function ModeModal({ isN3OrAdmin, onSelectAuto, onSelectCoord, onClose }: {
  isN3OrAdmin: boolean;
  onSelectAuto: () => void;
  onSelectCoord: () => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-2xl shadow-2xl w-[420px] p-6 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">Nova investigação</h3>
          <p className="text-xs text-gray-500 mt-0.5">Escolha o modo de investigação</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <button onClick={onSelectAuto} className="flex flex-col items-center gap-2 p-4 border-2 border-violet-200 bg-violet-50 text-violet-800 rounded-xl hover:border-violet-400 transition-colors text-left">
            <Zap size={20} className="text-violet-600" />
            <div>
              <p className="text-xs font-semibold">Automático</p>
              <p className="text-[11px] text-violet-600 mt-0.5">IA analisa todos os domínios em paralelo</p>
            </div>
          </button>
          <button
            onClick={isN3OrAdmin ? onSelectCoord : undefined}
            disabled={!isN3OrAdmin}
            className={`flex flex-col items-center gap-2 p-4 border-2 rounded-xl transition-colors text-left ${isN3OrAdmin ? "border-brand-200 bg-brand-50 text-brand-800 hover:border-brand-400" : "border-gray-100 bg-gray-50 text-gray-400 cursor-not-allowed"}`}
          >
            <GitMerge size={20} className={isN3OrAdmin ? "text-brand-600" : "text-gray-300"} />
            <div>
              <p className="text-xs font-semibold">Coordenado</p>
              <p className={`text-[11px] mt-0.5 ${isN3OrAdmin ? "text-brand-600" : "text-gray-400"}`}>
                {isN3OrAdmin ? "Especialistas por domínio, consolidação N3" : "Requer analyst_n2 ou admin"}
              </p>
            </div>
          </button>
        </div>
        <div className="flex justify-end">
          <button onClick={onClose} className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5">Cancelar</button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function MultiDomainPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const tenantRole = useAuthStore((s) => s.tenantRole);
  const handoffState = location.state as { context?: string; suggested_query?: string } | null;
  const isN3OrAdmin = tenantRole === "admin" || tenantRole === "analyst_n2";

  const [activeTab, setActiveTab] = useState<"auto" | "coord" | "history">("auto");
  const [showModeModal, setShowModeModal] = useState(false);

  // CrossDomain (Automático) state
  const [cdProblem, setCdProblem] = useState(handoffState?.suggested_query?.slice(0, 500) ?? "");
  const [cdSelectedDomains, setCdSelectedDomains] = useState<Set<CrossDomainAgentType>>(new Set(["firewall", "network", "n3", "rmm"]));
  const [cdActiveSessionId, setCdActiveSessionId] = useState<string | null>(null);

  // Composite (Coordenado) state
  const [showCompositeCreate, setShowCompositeCreate] = useState(false);
  const [compositeActiveId, setCompositeActiveId] = useState<string | null>(null);

  // Permissions
  const { data: myProfile } = useQuery({
    queryKey: ["my-perm-profile"],
    queryFn: async () => {
      const me = await import("../api/client").then((m) => m.default.get("/auth/me").then((r) => r.data));
      return permissionsApi.getUserCategoryProfile(me.id).catch(() => null);
    },
    staleTime: 60_000,
  });

  const allowedDomains: CrossDomainAgentType[] = (() => {
    if (!myProfile) return ["firewall", "network", "n3", "rmm"];
    const cats = myProfile.category_roles.map((cr: { category: string }) => cr.category);
    const map: Partial<Record<string, CrossDomainAgentType>> = {
      firewall: "firewall", switch: "network", routing: "network", server: "n3", hypervisor: "n3",
    };
    const allowed = new Set<CrossDomainAgentType>(cats.map((c: string) => map[c]).filter(Boolean) as CrossDomainAgentType[]);
    if (myProfile.tenant_role === "admin") return ["firewall", "network", "n3", "rmm"];
    return allowed.size > 0 ? Array.from(allowed) : ["firewall", "network", "n3", "rmm"];
  })();

  const toggleCdDomain = (d: CrossDomainAgentType) =>
    setCdSelectedDomains((prev) => { const n = new Set(prev); n.has(d) ? n.delete(d) : n.add(d); return n; });

  const cdStartMut = useMutation({
    mutationFn: () => crossDomainApi.start({ problem_description: cdProblem.trim(), domains: Array.from(cdSelectedDomains) }),
    onSuccess: (s) => {
      qc.setQueryData(["cross-domain", s.id], s);
      qc.invalidateQueries({ queryKey: ["cross-domain-list"] });
      setCdActiveSessionId(s.id);
    },
    onError: () => toast.error("Erro ao iniciar investigação."),
  });

  // Data
  const { data: cdList = [] } = useQuery({
    queryKey: ["cross-domain-list"],
    queryFn: crossDomainApi.list,
    enabled: activeTab === "history",
  });

  const { data: compositeList = [], isLoading: compositeListLoading } = useQuery({
    queryKey: ["composite-list"],
    queryFn: compositeApi.list,
    enabled: activeTab === "coord" || activeTab === "history",
  });

  const { data: compositeActiveInv } = useQuery({
    queryKey: ["composite", compositeActiveId],
    queryFn: () => compositeApi.get(compositeActiveId!),
    enabled: !!compositeActiveId,
    refetchInterval: (query) => {
      const data = (query as { state?: { data?: CompositeInvestigation } }).state?.data;
      if (!data) return false;
      return data.status === "active" || data.status === "consolidating" ? 3000 : false;
    },
  });

  // Combined history
  const combinedHistory = [
    ...cdList.map((s) => ({ type: "auto" as const, id: s.id, title: s.problem_description, created_at: s.created_at, status: s.status })),
    ...compositeList.map((s) => ({ type: "coord" as const, id: s.id, title: s.symptom, created_at: s.created_at, status: s.status })),
  ].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

  const handleCompositeCreated = (inv: CompositeInvestigation) => {
    qc.setQueryData(["composite", inv.id], inv);
    qc.invalidateQueries({ queryKey: ["composite-list"] });
    setShowCompositeCreate(false);
    setCompositeActiveId(inv.id);
  };

  const handleHistoryClick = (item: (typeof combinedHistory)[0]) => {
    if (item.type === "auto") {
      setActiveTab("auto");
      setCdActiveSessionId(item.id);
    } else {
      setActiveTab("coord");
      setCompositeActiveId(item.id);
    }
  };

  const tabs = [
    { id: "auto" as const, label: "Automático", Icon: Zap },
    { id: "coord" as const, label: "Coordenado", Icon: GitMerge },
    { id: "history" as const, label: "Histórico", Icon: History },
  ];

  return (
    <PageWrapper title="Investigação Multi-domínio" subtitle="Investigue problemas em múltiplos domínios de infraestrutura">
      <div className="max-w-2xl mx-auto space-y-4">

        {handoffState?.context && (() => {
          // context format: "[Contexto: <title>]\n\n<body>" or just "<body>"
          const ctxMatch = handoffState.context.match(/^\[Contexto:\s*(.+?)\]\n\n([\s\S]*)$/);
          const ctxTitle  = ctxMatch ? ctxMatch[1] : null;
          const ctxBody   = ctxMatch ? ctxMatch[2] : handoffState.context;
          return (
            <div className="flex items-start gap-2 bg-brand-50 border border-brand-200 rounded-xl px-4 py-3">
              <Sparkles size={13} className="text-brand-500 shrink-0 mt-0.5" />
              <div className="min-w-0">
                <p className="text-xs font-semibold text-brand-700">
                  Contexto importado do Assistente IA
                  {ctxTitle && <span className="ml-1.5 font-normal text-brand-600">— {ctxTitle}</span>}
                </p>
                <p className="text-xs text-brand-600 mt-0.5 line-clamp-2">{ctxBody}</p>
              </div>
            </div>
          );
        })()}

        {/* Tab bar */}
        <div className="flex items-center gap-2">
          <div className="flex gap-1 border-b border-gray-200 flex-1">
            {tabs.map(({ id, label, Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`flex items-center gap-1.5 text-xs px-3 py-2 border-b-2 transition-colors ${activeTab === id ? "border-violet-500 text-violet-700 font-medium" : "border-transparent text-gray-500 hover:text-gray-700"}`}
              >
                <Icon size={12} /> {label}
              </button>
            ))}
          </div>
          <button
            onClick={() => setShowModeModal(true)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-violet-600 text-white rounded-lg hover:bg-violet-700 shrink-0 mb-0.5"
          >
            <Plus size={12} /> Nova investigação
          </button>
        </div>

        {/* ── Automático tab ──────────────────────────────────────── */}
        {activeTab === "auto" && (
          cdActiveSessionId ? (
            <AutoSessionDetail sessionId={cdActiveSessionId} onBack={() => setCdActiveSessionId(null)} />
          ) : (
            <div className="space-y-5">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-gray-700">Descreva o problema</label>
                <textarea
                  value={cdProblem}
                  onChange={(e) => setCdProblem(e.target.value)}
                  rows={4}
                  placeholder="Ex: Lentidão generalizada desde 14h — usuários relatam timeout ao acessar sistemas internos"
                  className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-700">
                  Domínios a investigar
                  <span className="ml-1 font-normal text-gray-400">(somente os que você tem permissão)</span>
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {(["firewall", "network", "n3", "rmm"] as CrossDomainAgentType[]).map((domain) => {
                    const cfg = DOMAIN_CONFIG[domain];
                    const Icon = cfg.icon;
                    const allowed = allowedDomains.includes(domain);
                    const selected = cdSelectedDomains.has(domain);
                    return (
                      <button
                        key={domain}
                        onClick={() => allowed && toggleCdDomain(domain)}
                        disabled={!allowed}
                        className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl border text-sm transition-colors text-left ${
                          !allowed ? "border-gray-100 bg-gray-50 text-gray-300 cursor-not-allowed"
                          : selected ? `border-current ${cfg.color} font-medium`
                          : "border-gray-200 text-gray-500 hover:border-gray-300 hover:bg-gray-50"
                        }`}
                      >
                        <Icon size={14} className="shrink-0" />
                        <span className="flex-1">{cfg.label}</span>
                        {!allowed && <span className="text-[10px]">🔒</span>}
                        {allowed && selected && <CheckCircle2 size={13} className="shrink-0" />}
                      </button>
                    );
                  })}
                </div>
              </div>
              <button
                onClick={() => cdStartMut.mutate()}
                disabled={!cdProblem.trim() || cdSelectedDomains.size === 0 || cdStartMut.isPending}
                className="w-full flex items-center justify-center gap-2 py-3 bg-violet-600 text-white text-sm font-medium rounded-xl hover:bg-violet-700 disabled:opacity-50"
              >
                {cdStartMut.isPending
                  ? <><Loader2 size={14} className="animate-spin" /> Iniciando investigações…</>
                  : <><Play size={14} /> Iniciar investigação em {cdSelectedDomains.size} domínio{cdSelectedDomains.size !== 1 ? "s" : ""}</>}
              </button>
            </div>
          )
        )}

        {/* ── Coordenado tab ──────────────────────────────────────── */}
        {activeTab === "coord" && (
          compositeActiveId && compositeActiveInv ? (
            <CoordDetail inv={compositeActiveInv} onBack={() => setCompositeActiveId(null)} />
          ) : (
            <div className="space-y-3">
              {isN3OrAdmin && (
                <div className="flex justify-end">
                  <button
                    onClick={() => setShowCompositeCreate(true)}
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-brand-600 text-white rounded-xl hover:bg-brand-700"
                  >
                    <Plus size={12} /> Nova investigação coordenada
                  </button>
                </div>
              )}
              {compositeListLoading && (
                <div className="flex items-center justify-center h-32 gap-2 text-gray-400 text-sm">
                  <Loader2 size={15} className="animate-spin" /> Carregando…
                </div>
              )}
              {!compositeListLoading && compositeList.length === 0 && (
                <div className="text-center py-16 text-gray-400">
                  <Users size={32} className="mx-auto mb-3 opacity-30" />
                  <p className="text-sm">Nenhuma investigação coordenada ainda.</p>
                  {isN3OrAdmin && <p className="text-xs mt-1">Crie uma para coordenar especialistas de múltiplos domínios.</p>}
                </div>
              )}
              {compositeList.map((inv) => (
                <CompositeListItem key={inv.id} inv={inv} onSelect={() => setCompositeActiveId(inv.id)} />
              ))}
            </div>
          )
        )}

        {/* ── Histórico tab ───────────────────────────────────────── */}
        {activeTab === "history" && (
          <div className="space-y-2">
            {combinedHistory.length === 0 && (
              <p className="text-xs text-gray-400 italic text-center py-8">Nenhuma investigação ainda.</p>
            )}
            {combinedHistory.map((item) => (
              <button
                key={`${item.type}-${item.id}`}
                onClick={() => handleHistoryClick(item)}
                className="w-full flex items-start gap-3 p-3 rounded-xl border border-gray-200 hover:border-violet-300 hover:bg-violet-50 transition-colors text-left"
              >
                <div className="shrink-0 mt-0.5">
                  {item.type === "auto" ? <Zap size={13} className="text-violet-400" /> : <GitMerge size={13} className="text-brand-400" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-gray-800 truncate">{item.title}</p>
                  <p className="text-[10px] text-gray-400 mt-0.5">{new Date(item.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${item.type === "auto" ? "bg-violet-100 text-violet-600" : "bg-brand-100 text-brand-600"}`}>
                    {item.type === "auto" ? "Auto" : "Coord"}
                  </span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                    item.status === "done" || item.status === "resolved" ? "bg-green-100 text-green-700"
                    : item.status === "partial" || item.status === "consolidating" ? "bg-amber-100 text-amber-700"
                    : "bg-brand-100 text-brand-700"
                  }`}>
                    {item.status === "done" ? "Concluída" : item.status === "resolved" ? "Resolvida"
                     : item.status === "partial" ? "Parcial" : item.status === "consolidating" ? "Consolidando" : "Ativa"}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {showModeModal && (
        <ModeModal
          isN3OrAdmin={isN3OrAdmin}
          onSelectAuto={() => { setShowModeModal(false); setActiveTab("auto"); setCdActiveSessionId(null); }}
          onSelectCoord={() => { setShowModeModal(false); setActiveTab("coord"); setShowCompositeCreate(true); }}
          onClose={() => setShowModeModal(false)}
        />
      )}
      {showCompositeCreate && (
        <CreateCompositeModal onClose={() => setShowCompositeCreate(false)} onCreate={handleCompositeCreated} />
      )}
    </PageWrapper>
  );
}
