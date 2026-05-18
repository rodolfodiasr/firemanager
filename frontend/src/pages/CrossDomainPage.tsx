import { useState, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Layers, Flame, Network, Server, Monitor, Play, Loader2,
  CheckCircle2, AlertTriangle, Clock, RefreshCw, Sparkles, ArrowRight,
  ChevronDown, ChevronRight, History, Trash2, Wrench, MessageSquare,
  RotateCcw, Send, GitMerge,
} from "lucide-react";
import { PageWrapper } from "../components/layout/PageWrapper";
import {
  crossDomainApi,
  type CrossDomainAgentType,
  type CrossDomainSession,
  type CrossDomainSubResult,
} from "../api/crossDomain";
import { permissionsApi } from "../api/permissions";
import { useQuery as useQ } from "@tanstack/react-query";
import toast from "react-hot-toast";

// ── Domínio config ────────────────────────────────────────────────────────────

const DOMAIN_CONFIG: Record<CrossDomainAgentType, { label: string; icon: typeof Flame; color: string; route: string }> = {
  firewall: { label: "Firewall",   icon: Flame,   color: "text-orange-600 bg-orange-50 border-orange-200", route: "/agent" },
  network:  { label: "Redes",      icon: Network,  color: "text-blue-600 bg-blue-50 border-blue-200",       route: "/network-agent" },
  n3:       { label: "Servidores", icon: Server,   color: "text-purple-600 bg-purple-50 border-purple-200", route: "/server-analysis" },
  rmm:      { label: "Estações",   icon: Monitor,  color: "text-green-600 bg-green-50 border-green-200",    route: "/rmm-agent" },
};

// ── SubResult card with iterative features ────────────────────────────────────

function SubResultCard({
  sub,
  sessionId,
  onNavigate,
  onRerun,
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
      {/* Header row */}
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none"
        onClick={() => sub.synthesis && setExpanded((v) => !v)}
      >
        <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 border ${cfg.color}`}>
          <Icon size={13} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-800">{cfg.label}</p>
          {sub.status === "done" && sub.synthesis && (
            <p className="text-xs text-gray-600 truncate">{sub.synthesis.slice(0, 80)}…</p>
          )}
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
            <button
              onClick={(e) => { e.stopPropagation(); onNavigate(); }}
              className="text-[11px] px-2 py-0.5 rounded border border-current opacity-70 hover:opacity-100 transition-opacity"
            >
              Abrir
            </button>
          )}
          {/* Re-run button */}
          {(sub.status === "done" || sub.status === "error") && (
            <button
              onClick={(e) => { e.stopPropagation(); setShowRerun((v) => !v); setShowChat(false); }}
              title="Re-executar domínio"
              className="opacity-60 hover:opacity-100 transition-opacity"
            >
              <RotateCcw size={12} />
            </button>
          )}
          {/* Chat button */}
          {sub.status === "done" && (
            <button
              onClick={(e) => { e.stopPropagation(); setShowChat((v) => !v); setShowRerun(false); }}
              title="Chat com este domínio"
              className="opacity-60 hover:opacity-100 transition-opacity"
            >
              <MessageSquare size={12} />
            </button>
          )}
          {sub.synthesis && (
            expanded
              ? <ChevronDown size={13} className="text-gray-400" />
              : <ChevronRight size={13} className="text-gray-400" />
          )}
        </div>
      </div>

      {/* Synthesis content */}
      {expanded && sub.synthesis && (
        <div className="px-4 pb-4 border-t border-current/20 pt-3">
          <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">{sub.synthesis}</p>
        </div>
      )}

      {/* Re-run panel */}
      {showRerun && (
        <div className="px-4 pb-4 border-t border-current/20 pt-3 space-y-2" onClick={(e) => e.stopPropagation()}>
          <p className="text-xs font-semibold text-gray-700">Re-executar análise</p>
          <textarea
            value={rerunCtx}
            onChange={(e) => setRerunCtx(e.target.value)}
            rows={2}
            placeholder="Contexto adicional (opcional) — ex: verifique também as regras de NAT"
            className="w-full border border-gray-300 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-violet-500 resize-none bg-white"
          />
          <div className="flex gap-2">
            <button
              onClick={() => { onRerun(sub.domain, rerunCtx.trim() || undefined); setShowRerun(false); setRerunCtx(""); }}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-violet-600 text-white rounded-lg hover:bg-violet-700"
            >
              <RotateCcw size={11} /> Re-executar
            </button>
            <button onClick={() => setShowRerun(false)} className="text-xs px-3 py-1.5 border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50">
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Chat panel */}
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
              placeholder={`Pergunte algo sobre ${cfg.label}…`}
              className="flex-1 border border-gray-300 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-violet-500 bg-white"
            />
            <button
              onClick={handleChat}
              disabled={!chatMsg.trim() || chatLoading}
              className="flex items-center gap-1 px-3 py-1.5 bg-violet-600 text-white text-xs rounded-lg hover:bg-violet-700 disabled:opacity-50"
            >
              {chatLoading ? <Loader2 size={11} className="animate-spin" /> : <Send size={11} />}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Session detail ────────────────────────────────────────────────────────────

function SessionDetail({ sessionId, onBack }: { sessionId: string; onBack: () => void }) {
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
    onError: () => toast.error("Erro ao correlacionar resultados."),
  });

  const rerunMut = useMutation({
    mutationFn: ({ domain, ctx }: { domain: CrossDomainAgentType; ctx?: string }) =>
      crossDomainApi.rerunDomain(sessionId, domain, ctx),
    onSuccess: (s) => {
      qc.setQueryData(["cross-domain", sessionId], s);
      toast.success("Re-análise iniciada.");
    },
    onError: () => toast.error("Erro ao re-executar domínio."),
  });

  const deleteMut = useMutation({
    mutationFn: () => crossDomainApi.delete(sessionId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cross-domain-list"] }); onBack(); },
  });

  if (isLoading || !session) {
    return (
      <div className="flex items-center justify-center h-64 gap-2 text-gray-500 text-sm">
        <Loader2 size={16} className="animate-spin" /> Carregando…
      </div>
    );
  }

  const anyDone = session.sub_results.some((s) => s.status === "done");

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <button onClick={onBack} className="text-xs text-gray-400 hover:text-gray-600 mb-1">← Voltar</button>
          <p className="text-sm font-semibold text-gray-800">{session.problem_description}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {new Date(session.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            session.status === "done"    ? "bg-green-100 text-green-700" :
            session.status === "partial" ? "bg-amber-100 text-amber-700" :
                                           "bg-brand-100 text-brand-700"
          }`}>
            {session.status === "done" ? "Concluída" : session.status === "partial" ? "Parcial" : "Em andamento"}
          </span>
          <button
            onClick={() => { if (confirm("Remover investigação?")) deleteMut.mutate(); }}
            className="text-gray-400 hover:text-red-500 transition-colors"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Sub-results */}
      <div className="space-y-2">
        {session.sub_results.map((sub) => (
          <SubResultCard
            key={sub.domain}
            sub={sub}
            sessionId={sessionId}
            onNavigate={() => {
              const cfg = DOMAIN_CONFIG[sub.domain];
              navigate(cfg.route, { state: { context: session.problem_description } });
            }}
            onRerun={(domain, ctx) => rerunMut.mutate({ domain, ctx })}
          />
        ))}
      </div>

      {/* Correlation — always show button when any domain done */}
      {anyDone && (
        <button
          onClick={() => correlateMut.mutate()}
          disabled={correlateMut.isPending}
          className="w-full flex items-center justify-center gap-2 py-2.5 bg-violet-600 text-white text-sm font-medium rounded-xl hover:bg-violet-700 disabled:opacity-50"
        >
          {correlateMut.isPending
            ? <><Loader2 size={13} className="animate-spin" /> Correlacionando…</>
            : session.correlation
            ? <><RefreshCw size={13} /> Re-correlacionar domínios</>
            : <><Sparkles size={13} /> Correlacionar e identificar causa raiz</>}
        </button>
      )}

      {session.correlation && (
        <div className="border border-violet-200 bg-violet-50 rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-violet-600" />
            <p className="text-xs font-semibold text-violet-700">Correlação IA — Causa raiz</p>
          </div>
          <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{session.correlation}</p>
        </div>
      )}

      {session.correlation && (
        <div className="space-y-2">
          <button
            onClick={() => navigate("/assistant", { state: { prefill: session.correlation } })}
            className="w-full flex items-center justify-center gap-2 py-2.5 border border-brand-300 text-brand-700 text-sm font-medium rounded-xl hover:bg-brand-50"
          >
            <ArrowRight size={13} /> Gerar Plano de Ação no Assistente IA
          </button>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => navigate("/remediation", {
                state: { prefill: session.correlation, source: "cross-domain", sessionId: session.id },
              })}
              className="flex items-center justify-center gap-2 py-2 border border-amber-300 text-amber-700 text-sm font-medium rounded-xl hover:bg-amber-50"
            >
              <Wrench size={13} /> Criar Remediação
            </button>
            <button
              onClick={() => navigate("/glpi", {
                state: { prefill: `Investigação Cruzada — ${session.problem_description}\n\n${session.correlation}` },
              })}
              className="flex items-center justify-center gap-2 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-xl hover:bg-gray-50"
            >
              <MessageSquare size={13} /> Criar Ticket IA
            </button>
          </div>
          <button
            onClick={() => navigate("/composite-investigation", {
              state: {
                symptom: session.problem_description,
                correlation: session.correlation,
                fromCrossDomain: true,
                crossDomainSessionId: session.id,
              },
            })}
            className="w-full flex items-center justify-center gap-2 py-2 border border-violet-300 text-violet-700 text-sm font-medium rounded-xl hover:bg-violet-50"
          >
            <GitMerge size={13} /> Escalar para Investigação Composta N3
          </button>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function CrossDomainPage() {
  const location = useLocation();
  const qc = useQueryClient();
  const handoffState = location.state as { context?: string; suggested_query?: string } | null;

  const [problem, setProblem] = useState(handoffState?.suggested_query?.slice(0, 500) ?? "");
  const [selectedDomains, setSelectedDomains] = useState<Set<CrossDomainAgentType>>(
    new Set(["firewall", "network", "n3", "rmm"])
  );
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [view, setView] = useState<"new" | "history">("new");

  const { data: myProfile } = useQ({
    queryKey: ["my-perm-profile"],
    queryFn: async () => {
      const me = await import("../api/client").then((m) => m.default.get("/auth/me").then((r) => r.data));
      return permissionsApi.getUserCategoryProfile(me.id).catch(() => null);
    },
    staleTime: 60_000,
  });

  const allowedDomains: CrossDomainAgentType[] = (() => {
    if (!myProfile) return ["firewall", "network", "n3", "rmm"];
    const cats = myProfile.category_roles.map((cr) => cr.category);
    const map: Partial<Record<string, CrossDomainAgentType>> = {
      firewall:   "firewall",
      switch:     "network",
      routing:    "network",
      server:     "n3",
      hypervisor: "n3",
    };
    const allowed = new Set<CrossDomainAgentType>(
      cats.map((c) => map[c]).filter(Boolean) as CrossDomainAgentType[]
    );
    if (myProfile.tenant_role === "admin") return ["firewall", "network", "n3", "rmm"];
    return allowed.size > 0 ? Array.from(allowed) : ["firewall", "network", "n3", "rmm"];
  })();

  const toggleDomain = (d: CrossDomainAgentType) =>
    setSelectedDomains((prev) => {
      const next = new Set(prev);
      next.has(d) ? next.delete(d) : next.add(d);
      return next;
    });

  const startMut = useMutation({
    mutationFn: () => crossDomainApi.start({
      problem_description: problem.trim(),
      domains: Array.from(selectedDomains),
    }),
    onSuccess: (s) => {
      qc.setQueryData(["cross-domain", s.id], s);
      qc.invalidateQueries({ queryKey: ["cross-domain-list"] });
      setActiveSessionId(s.id);
    },
    onError: () => toast.error("Erro ao iniciar investigação cruzada."),
  });

  const { data: history = [] } = useQuery({
    queryKey: ["cross-domain-list"],
    queryFn: crossDomainApi.list,
    enabled: view === "history",
  });

  if (activeSessionId) {
    return (
      <PageWrapper title="Investigação Cruzada">
        <div className="max-w-2xl mx-auto">
          <SessionDetail sessionId={activeSessionId} onBack={() => setActiveSessionId(null)} />
        </div>
      </PageWrapper>
    );
  }

  return (
    <PageWrapper
      title="Investigação Cruzada"
      subtitle="Investigue um problema em múltiplos domínios simultaneamente"
    >
      <div className="max-w-2xl mx-auto space-y-5">
        {handoffState?.context && (
          <div className="flex items-start gap-2 bg-brand-50 border border-brand-200 rounded-xl px-4 py-3">
            <Sparkles size={13} className="text-brand-500 shrink-0 mt-0.5" />
            <div className="min-w-0">
              <p className="text-xs font-semibold text-brand-700">Contexto importado do Assistente IA</p>
              <p className="text-xs text-brand-600 mt-0.5 line-clamp-2">{handoffState.context}</p>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 border-b border-gray-200">
          {(["new", "history"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setView(tab)}
              className={`flex items-center gap-1.5 text-xs px-3 py-2 border-b-2 transition-colors ${
                view === tab
                  ? "border-violet-500 text-violet-700 font-medium"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab === "new" ? <><Layers size={12} /> Nova investigação</> : <><History size={12} /> Histórico</>}
            </button>
          ))}
        </div>

        {view === "new" && (
          <div className="space-y-5">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-700">Descreva o problema</label>
              <textarea
                value={problem}
                onChange={(e) => setProblem(e.target.value)}
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
                  const selected = selectedDomains.has(domain);
                  return (
                    <button
                      key={domain}
                      onClick={() => allowed && toggleDomain(domain)}
                      disabled={!allowed}
                      className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl border text-sm transition-colors text-left ${
                        !allowed
                          ? "border-gray-100 bg-gray-50 text-gray-300 cursor-not-allowed"
                          : selected
                          ? `border-current ${cfg.color} font-medium`
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
              onClick={() => startMut.mutate()}
              disabled={!problem.trim() || selectedDomains.size === 0 || startMut.isPending}
              className="w-full flex items-center justify-center gap-2 py-3 bg-violet-600 text-white text-sm font-medium rounded-xl hover:bg-violet-700 disabled:opacity-50"
            >
              {startMut.isPending
                ? <><Loader2 size={14} className="animate-spin" /> Iniciando investigações…</>
                : <><Play size={14} /> Iniciar investigação em {selectedDomains.size} domínio{selectedDomains.size !== 1 ? "s" : ""}</>}
            </button>
          </div>
        )}

        {view === "history" && (
          <div className="space-y-2">
            {history.length === 0 && (
              <p className="text-xs text-gray-400 italic text-center py-8">Nenhuma investigação cruzada ainda.</p>
            )}
            {history.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveSessionId(s.id)}
                className="w-full flex items-start gap-3 p-3 rounded-xl border border-gray-200 hover:border-violet-300 hover:bg-violet-50 transition-colors text-left"
              >
                <div className="flex gap-1 shrink-0 mt-0.5">
                  {s.domains.map((d) => {
                    const Ic = DOMAIN_CONFIG[d].icon;
                    return <Ic key={d} size={11} className="text-gray-400" />;
                  })}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-gray-800 truncate">{s.problem_description}</p>
                  <p className="text-[10px] text-gray-400 mt-0.5">
                    {new Date(s.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
                  </p>
                </div>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full shrink-0 font-medium ${
                  s.status === "done"    ? "bg-green-100 text-green-700" :
                  s.status === "partial" ? "bg-amber-100 text-amber-700" :
                                           "bg-brand-100 text-brand-700"
                }`}>
                  {s.status === "done" ? "Concluída" : s.status === "partial" ? "Parcial" : "Em andamento"}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
