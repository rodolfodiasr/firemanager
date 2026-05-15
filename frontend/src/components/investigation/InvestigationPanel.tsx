import { useState, useRef, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Search, Play, ChevronDown, ChevronRight, Loader2,
  CheckCircle2, AlertTriangle, Share2,
  MessageSquare, Terminal, Layers, ArrowRight, RefreshCw,
  Check, X, Pencil, CheckSquare,
} from "lucide-react";
import { investigationsApi, type InvestigationSession, type InvestigationPhase, type CommandState } from "../../api/investigations";
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

// ── Command row ───────────────────────────────────────────────────────────────

function CommandRow({
  cs,
  phaseStatus,
  onApprove,
  onReject,
  onEdit,
  isUpdating,
}: {
  cs: CommandState;
  phaseStatus: string;
  onApprove: () => void;
  onReject: () => void;
  onEdit: (text: string) => void;
  isUpdating: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(cs.edited ?? cs.command);

  const displayCmd = cs.edited ?? cs.command;
  const isApproved = cs.status === "approved";
  const isRejected = cs.status === "rejected";
  const canEdit = phaseStatus === "pending";

  function commitEdit() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== (cs.edited ?? cs.command)) {
      onEdit(trimmed);
    }
    setEditing(false);
  }

  return (
    <div className={`flex items-start gap-2 p-2 rounded-lg border transition-colors ${
      isRejected
        ? "bg-red-50 border-red-200 opacity-60"
        : isApproved
        ? "bg-green-50 border-green-200"
        : "bg-gray-50 border-gray-200"
    }`}>
      {/* Status indicator */}
      <div className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
        isRejected ? "bg-red-400" : isApproved ? "bg-green-500" : "bg-gray-300"
      }`}>
        {isApproved && <Check size={10} className="text-white" />}
        {isRejected && <X size={10} className="text-white" />}
      </div>

      {/* Command text / edit field */}
      <div className="flex-1 min-w-0">
        {editing ? (
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitEdit();
              if (e.key === "Escape") { setDraft(cs.edited ?? cs.command); setEditing(false); }
            }}
            className="w-full text-xs font-mono bg-white border border-brand-400 rounded px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        ) : (
          <p className={`text-xs font-mono break-all ${
            isRejected ? "line-through text-gray-400" : "text-gray-800"
          }`}>
            {displayCmd}
            {cs.edited && cs.edited !== cs.command && (
              <span className="ml-1 text-[10px] text-brand-500 font-sans font-medium">(editado)</span>
            )}
          </p>
        )}
      </div>

      {/* Action buttons — only when phase is pending */}
      {canEdit && !editing && (
        <div className="flex items-center gap-1 shrink-0">
          {isUpdating ? (
            <Loader2 size={11} className="animate-spin text-gray-400" />
          ) : (
            <>
              <button
                title="Aprovar"
                onClick={onApprove}
                className={`p-0.5 rounded hover:bg-green-100 ${isApproved ? "text-green-600" : "text-gray-400 hover:text-green-600"}`}
              >
                <Check size={13} />
              </button>
              <button
                title="Rejeitar"
                onClick={onReject}
                className={`p-0.5 rounded hover:bg-red-100 ${isRejected ? "text-red-500" : "text-gray-400 hover:text-red-500"}`}
              >
                <X size={13} />
              </button>
              <button
                title="Editar comando"
                onClick={() => { setDraft(cs.edited ?? cs.command); setEditing(true); }}
                className="p-0.5 rounded hover:bg-brand-100 text-gray-400 hover:text-brand-600"
              >
                <Pencil size={11} />
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}


// ── Phase card ────────────────────────────────────────────────────────────────

function PhaseCard({
  phase,
  onRun,
  onUpdateCommand,
  isRunning,
  isBlocked,
  updatingCmd,
}: {
  phase: InvestigationPhase;
  onRun: () => void;
  onUpdateCommand: (cmdIdx: number, data: { status?: "pending" | "approved" | "rejected"; edited?: string | null }) => void;
  isRunning: boolean;
  isBlocked?: boolean;
  updatingCmd: number | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const isDone = phase.status === "done";
  const isPending = phase.status === "pending";

  const states = phase.command_states ?? phase.commands.map((cmd, idx) => ({
    idx, command: cmd, edited: null, status: "pending" as const,
  }));

  const approvedCount = states.filter((cs) => cs.status === "approved").length;
  const rejectedCount = states.filter((cs) => cs.status === "rejected").length;
  const pendingCount = states.filter((cs) => cs.status === "pending").length;
  const runnableCount = states.filter((cs) => cs.status !== "rejected").length;

  const allApproved = states.length > 0 && states.every((cs) => cs.status === "approved");
  const hasPending = pendingCount > 0;

  function approveAll() {
    states.forEach((cs) => {
      if (cs.status !== "approved") {
        onUpdateCommand(cs.idx, { status: "approved" });
      }
    });
  }

  return (
    <div className={`border rounded-xl overflow-hidden ${
      isDone ? "border-green-200 bg-green-50" : "border-gray-200 bg-white"
    }`}>
      {/* Header */}
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none"
        onClick={() => (isDone || isPending) && setExpanded((v) => !v)}
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
          {isDone || isPending
            ? (expanded ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />)
            : null}
        </div>
      </div>

      {/* Commands section — expandable */}
      {(isPending || (isDone && expanded)) && (
        <div className="px-4 pb-3 border-t border-gray-100 pt-2 space-y-2">
          {/* Toolbar */}
          {isPending && (
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-medium text-gray-500 flex items-center gap-1">
                <Terminal size={11} /> Comandos ({states.length})
                {approvedCount > 0 && <span className="ml-1 text-green-600">{approvedCount} aprovado(s)</span>}
                {rejectedCount > 0 && <span className="ml-1 text-red-500">{rejectedCount} rejeitado(s)</span>}
              </p>
              <div className="flex items-center gap-2">
                {hasPending && (
                  <button
                    onClick={(e) => { e.stopPropagation(); approveAll(); }}
                    className="flex items-center gap-1 text-[11px] text-brand-600 hover:text-brand-800 font-medium"
                  >
                    <CheckSquare size={12} /> Aprovar todos
                  </button>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); onRun(); }}
                  disabled={isRunning || isBlocked || runnableCount === 0}
                  title={isBlocked ? "Aguarde a fase em execução terminar" : undefined}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
                >
                  {isRunning ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                  {isRunning ? "Executando..." : `Executar${allApproved ? " aprovados" : ""}${runnableCount < states.length ? ` (${runnableCount})` : ""}`}
                </button>
              </div>
            </div>
          )}

          {/* Per-command rows */}
          <div className="space-y-1.5">
            {states.map((cs) => (
              <CommandRow
                key={cs.idx}
                cs={cs}
                phaseStatus={phase.status}
                isUpdating={updatingCmd === cs.idx}
                onApprove={() => onUpdateCommand(cs.idx, { status: cs.status === "approved" ? "pending" : "approved" })}
                onReject={() => onUpdateCommand(cs.idx, { status: cs.status === "rejected" ? "pending" : "rejected" })}
                onEdit={(text) => onUpdateCommand(cs.idx, { edited: text })}
              />
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

  const updateCmdMut = useMutation({
    mutationFn: ({
      phaseNumber,
      cmdIdx,
      data,
    }: {
      phaseNumber: number;
      cmdIdx: number;
      data: { status?: "pending" | "approved" | "rejected"; edited?: string | null };
    }) => investigationsApi.updateCommand(sessionId!, phaseNumber, cmdIdx, data),
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

  const continueMut = useMutation({
    mutationFn: () => investigationsApi.continue(sessionId!),
    onSuccess: (s) => {
      qc.setQueryData(["investigation", sessionId], s);
      setTab("phases");
    },
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
  const donePhasesCount = session.phases.filter((p) => p.status === "done").length;

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Investigação ativa</p>
          {targetLabel && (
            <p className="text-[11px] text-brand-600 font-medium truncate">{targetLabel}</p>
          )}
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
          {(() => {
            // Block all run buttons while any phase is executing or a mutation is pending
            const anyExecuting = session.phases.some((p) => p.status === "executing") || runPhaseMut.isPending;
            return session.phases.map((phase) => (
              <PhaseCard
                key={phase.id}
                phase={phase}
                onRun={() => runPhaseMut.mutate(phase.phase_number)}
                onUpdateCommand={(cmdIdx, data) =>
                  updateCmdMut.mutate({ phaseNumber: phase.phase_number, cmdIdx, data })
                }
                isRunning={
                  anyExecuting &&
                  (runPhaseMut.variables === phase.phase_number || phase.status === "executing")
                }
                isBlocked={anyExecuting && runPhaseMut.variables !== phase.phase_number && phase.status !== "executing"}
                updatingCmd={
                  updateCmdMut.isPending &&
                  (updateCmdMut.variables as any)?.phaseNumber === phase.phase_number
                    ? (updateCmdMut.variables as any)?.cmdIdx
                    : null
                }
              />
            ));
          })()}

          {/* Synthesis / actions */}
          {allPhasesDone && (
            <div className="border border-brand-200 bg-brand-50 rounded-xl p-4 space-y-3">
              {session.synthesis && (
                <>
                  <p className="text-xs font-semibold text-brand-700">Síntese final</p>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                    {session.synthesis}
                  </p>
                  <div className="border-t border-brand-200 pt-2" />
                </>
              )}

              {/* Continue investigation — always available when all phases done */}
              <button
                onClick={() => continueMut.mutate()}
                disabled={continueMut.isPending}
                className="w-full flex items-center justify-center gap-2 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
              >
                {continueMut.isPending
                  ? <><Loader2 size={13} className="animate-spin" /> Planejando novas fases...</>
                  : <><RefreshCw size={13} /> Continuar Investigação</>}
              </button>
              {continueMut.isError && (
                <p className="text-xs text-red-600 text-center">
                  {(continueMut.error as any)?.response?.data?.detail ?? "Erro ao gerar novas fases. Tente novamente."}
                </p>
              )}

              {!session.synthesis && (
                <button
                  onClick={() => synthesizeMut.mutate()}
                  disabled={synthesizeMut.isPending}
                  className="w-full flex items-center justify-center gap-2 py-2 border border-brand-300 text-brand-700 text-sm font-medium rounded-lg hover:bg-brand-100 disabled:opacity-50"
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
