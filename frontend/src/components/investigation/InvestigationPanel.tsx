import { useState, useRef, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Search, Play, ChevronDown, ChevronRight, Loader2,
  CheckCircle2, AlertTriangle, ExternalLink, Share2,
  MessageSquare, Terminal, Layers, ArrowRight,
} from "lucide-react";
import { investigationsApi, type InvestigationSession, type InvestigationPhase } from "../../api/investigations";
import { useNavigate } from "react-router-dom";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface InvestigationTarget {
  device_id?: string;
  server_id?: string;
  integration_ids?: string[];
}

export type InvestigationAgentType = "network" | "firewall" | "n3";

interface InvestigationPanelProps {
  agentType: InvestigationAgentType;
  target: InvestigationTarget;
  targetLabel?: string;
  sessionId?: string;
  onSessionCreated?: (sessionId: string) => void;
}

// ── Phase card ────────────────────────────────────────────────────────────────

function PhaseCard({
  phase,
  onRun,
  isRunning,
}: {
  phase: InvestigationPhase;
  onRun: () => void;
  isRunning: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const isDone = phase.status === "done";
  const isPending = phase.status === "pending";

  return (
    <div className={`border rounded-xl overflow-hidden ${
      isDone ? "border-green-200 bg-green-50" : "border-gray-200 bg-white"
    }`}>
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none"
        onClick={() => isDone && setExpanded((v) => !v)}
      >
        <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${
          isDone ? "bg-green-500 text-white" : "bg-gray-200 text-gray-600"
        }`}>
          {isDone ? <CheckCircle2 size={14} /> : phase.phase_number}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-800">{phase.phase_name}</p>
          {phase.phase_purpose && (
            <p className="text-xs text-gray-500 truncate">{phase.phase_purpose}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {isPending && (
            <button
              onClick={(e) => { e.stopPropagation(); onRun(); }}
              disabled={isRunning}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
            >
              {isRunning ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
              {isRunning ? "Executando..." : "Executar fase"}
            </button>
          )}
          {isDone && (
            expanded ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />
          )}
        </div>
      </div>

      {/* Commands preview (always visible for pending) */}
      {(isPending || (isDone && expanded)) && phase.commands.length > 0 && (
        <div className="px-4 pb-3 border-t border-gray-100 pt-2">
          <p className="text-xs font-medium text-gray-500 mb-1.5 flex items-center gap-1">
            <Terminal size={11} /> Comandos ({phase.commands.length})
          </p>
          <div className="bg-gray-900 rounded-lg p-2.5 space-y-0.5">
            {phase.commands.map((cmd, i) => (
              <p key={i} className="text-xs font-mono text-green-400">{cmd}</p>
            ))}
          </div>
        </div>
      )}

      {/* Analysis (expanded done phase) */}
      {isDone && expanded && phase.analysis && (
        <div className="px-4 pb-4 border-t border-gray-100 pt-3">
          <p className="text-xs font-medium text-gray-500 mb-2">Análise</p>
          <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
            {phase.analysis}
          </div>
          {phase.findings.length > 0 && (
            <div className="mt-3 space-y-1">
              {phase.findings.slice(0, 5).map((f, i) => (
                <div key={i} className="flex items-start gap-1.5 text-xs text-gray-600">
                  <ArrowRight size={11} className="text-brand-500 mt-0.5 shrink-0" />
                  {f}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Chat message ──────────────────────────────────────────────────────────────

function ChatMessage({ role, content }: { role: string; content: string }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
        isUser
          ? "bg-brand-600 text-white rounded-br-sm"
          : "bg-gray-100 text-gray-800 rounded-bl-sm"
      }`}>
        <div className="whitespace-pre-wrap">{content}</div>
      </div>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export function InvestigationPanel({
  agentType,
  target,
  targetLabel,
  sessionId: externalSessionId,
  onSessionCreated,
}: InvestigationPanelProps) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const bottomRef = useRef<HTMLDivElement>(null);

  const [sessionId, setSessionId] = useState<string | null>(externalSessionId ?? null);
  const [problem, setProblem] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [tab, setTab] = useState<"phases" | "chat">("phases");

  const { data: session, isLoading: loadingSession } = useQuery({
    queryKey: ["investigation", sessionId],
    queryFn: () => investigationsApi.get(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const data = (query as { state?: { data?: InvestigationSession } }).state?.data;
      if (!data) return false;
      const hasExecuting = data.phases?.some((p: InvestigationPhase) => p.status === "executing");
      return hasExecuting ? 1500 : false;
    },
  });

  // Scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.messages?.length]);

  const startMut = useMutation({
    mutationFn: () =>
      investigationsApi.start({
        problem_description: problem.trim(),
        agent_type: agentType,
        ...target,
      }),
    onSuccess: (s) => {
      setSessionId(s.id);
      onSessionCreated?.(s.id);
      qc.setQueryData(["investigation", s.id], s);
      setProblem("");
    },
  });

  const runPhaseMut = useMutation({
    mutationFn: (phaseNumber: number) =>
      investigationsApi.runPhase(sessionId!, phaseNumber),
    onSuccess: (s) => {
      qc.setQueryData(["investigation", sessionId], s);
    },
  });

  const chatMut = useMutation({
    mutationFn: (msg: string) => investigationsApi.sendMessage(sessionId!, msg),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["investigation", sessionId] });
      setChatInput("");
    },
  });

  const synthesizeMut = useMutation({
    mutationFn: () => investigationsApi.synthesize(sessionId!),
    onSuccess: (s) => qc.setQueryData(["investigation", sessionId], s),
  });

  const exportMut = useMutation({
    mutationFn: () => investigationsApi.exportRunbook(sessionId!),
    onSuccess: (r) => navigate(`/assistant?session=${r.assistant_session_id}`),
  });

  // ── No session yet — start form ───────────────────────────────────────────
  if (!sessionId) {
    return (
      <div className="flex flex-col gap-4 h-full">
        <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
          <Search size={16} className="text-brand-500" />
          Diagnóstico Iterativo
        </div>
        {targetLabel && (
          <p className="text-xs text-gray-500">
            Alvo: <span className="font-medium text-gray-700">{targetLabel}</span>
          </p>
        )}
        <textarea
          value={problem}
          onChange={(e) => setProblem(e.target.value)}
          rows={5}
          placeholder={
            agentType === "n3"
              ? "Descreva o problema no servidor: ex. CPU alta nos últimos 30 min, processo consumindo 90% de um core..."
              : agentType === "firewall"
              ? "Descreva o problema: ex. Usuários sem acesso à internet desde 14h, regras parecem corretas..."
              : "Descreva o problema de rede: ex. Hosts na VLAN 100 sem conectividade com VLAN 200..."
          }
          className="flex-1 border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
        />
        {startMut.isError && (
          <p className="text-xs text-red-600">
            {(startMut.error as any)?.response?.data?.detail ?? "Erro ao iniciar investigação."}
          </p>
        )}
        <button
          onClick={() => startMut.mutate()}
          disabled={!problem.trim() || startMut.isPending}
          className="flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-xl hover:bg-brand-700 disabled:opacity-50"
        >
          {startMut.isPending
            ? <><Loader2 size={14} className="animate-spin" /> Planejando investigação...</>
            : <><Search size={14} /> Iniciar Diagnóstico</>}
        </button>
      </div>
    );
  }

  // ── Loading ────────────────────────────────────────────────────────────────
  if (loadingSession || !session) {
    return (
      <div className="flex items-center justify-center h-full gap-2 text-gray-500 text-sm">
        <Loader2 size={16} className="animate-spin" />
        Carregando investigação...
      </div>
    );
  }

  const allPhasesDone = session.phases.length > 0 &&
    session.phases.every((p) => p.status === "done");
  const nextPendingPhase = session.phases.find((p) => p.status === "pending");
  const donePhasesCount = session.phases.filter((p) => p.status === "done").length;

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Investigação ativa</p>
          <p className="text-sm font-medium text-gray-800 truncate">{session.problem_description}</p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            session.status === "done"
              ? "bg-green-100 text-green-700"
              : session.status === "active"
              ? "bg-brand-100 text-brand-700"
              : "bg-gray-100 text-gray-600"
          }`}>
            {session.status === "done" ? "Concluído" : session.status === "active" ? "Em andamento" : "Planejando"}
          </span>
        </div>
      </div>

      {/* Cross-domain alert */}
      {session.cross_domain_detected && session.cross_domain_hint && (
        <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl p-3">
          <AlertTriangle size={14} className="text-amber-600 shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-xs font-semibold text-amber-800">Problema multi-domínio detectado</p>
            <p className="text-xs text-amber-700 mt-0.5">{session.cross_domain_hint}</p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 pb-0">
        <button
          onClick={() => setTab("phases")}
          className={`flex items-center gap-1.5 text-xs px-3 py-2 border-b-2 transition-colors ${
            tab === "phases"
              ? "border-brand-500 text-brand-700 font-medium"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          <Layers size={12} />
          Fases ({donePhasesCount}/{session.phases.length})
        </button>
        <button
          onClick={() => setTab("chat")}
          className={`flex items-center gap-1.5 text-xs px-3 py-2 border-b-2 transition-colors ${
            tab === "chat"
              ? "border-brand-500 text-brand-700 font-medium"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          <MessageSquare size={12} />
          Chat
          {session.messages.length > 0 && (
            <span className="bg-brand-100 text-brand-700 px-1.5 py-0.5 rounded-full text-[10px] font-medium">
              {session.messages.length}
            </span>
          )}
        </button>
      </div>

      {/* Phases tab */}
      {tab === "phases" && (
        <div className="flex-1 flex flex-col gap-2.5 overflow-y-auto min-h-0">
          {session.phases.map((phase) => (
            <PhaseCard
              key={phase.id}
              phase={phase}
              onRun={() => runPhaseMut.mutate(phase.phase_number)}
              isRunning={runPhaseMut.isPending && runPhaseMut.variables === phase.phase_number}
            />
          ))}

          {/* Synthesis / actions */}
          {allPhasesDone && (
            <div className="border border-brand-200 bg-brand-50 rounded-xl p-4 space-y-3">
              {session.synthesis ? (
                <>
                  <p className="text-xs font-semibold text-brand-700">Síntese final</p>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                    {session.synthesis}
                  </p>
                </>
              ) : (
                <button
                  onClick={() => synthesizeMut.mutate()}
                  disabled={synthesizeMut.isPending}
                  className="w-full flex items-center justify-center gap-2 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
                >
                  {synthesizeMut.isPending
                    ? <><Loader2 size={13} className="animate-spin" /> Gerando síntese...</>
                    : "Gerar síntese final"}
                </button>
              )}
              <button
                onClick={() => exportMut.mutate()}
                disabled={exportMut.isPending}
                className="w-full flex items-center justify-center gap-2 py-2 border border-brand-300 text-brand-700 text-sm font-medium rounded-lg hover:bg-brand-100 disabled:opacity-50"
              >
                {exportMut.isPending
                  ? <><Loader2 size={13} className="animate-spin" /> Exportando...</>
                  : <><Share2 size={13} /> Exportar Runbook para AI Assistant</>}
              </button>
            </div>
          )}

          {/* New investigation */}
          <button
            onClick={() => setSessionId(null)}
            className="text-xs text-gray-400 hover:text-gray-600 self-start mt-1"
          >
            ← Nova investigação
          </button>
        </div>
      )}

      {/* Chat tab */}
      {tab === "chat" && (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto flex flex-col gap-2.5 pb-2">
            {session.messages.map((m) => (
              <ChatMessage key={m.id} role={m.role} content={m.content} />
            ))}
            {chatMut.isPending && (
              <div className="flex justify-start">
                <div className="bg-gray-100 text-gray-500 text-xs px-3 py-2 rounded-2xl rounded-bl-sm flex items-center gap-1.5">
                  <Loader2 size={12} className="animate-spin" /> Analisando...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="flex gap-2 pt-2 border-t border-gray-100">
            <input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && chatInput.trim()) {
                  e.preventDefault();
                  chatMut.mutate(chatInput.trim());
                }
              }}
              placeholder="Pergunte sobre a investigação..."
              className="flex-1 border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <button
              onClick={() => chatInput.trim() && chatMut.mutate(chatInput.trim())}
              disabled={!chatInput.trim() || chatMut.isPending}
              className="px-3 py-2 bg-brand-600 text-white rounded-xl hover:bg-brand-700 disabled:opacity-50"
            >
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
