import { useState, useRef, useEffect } from "react";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Terminal,
  X,
  Send,
  Loader2,
} from "lucide-react";
import type { DiagnosticAnalysis, DiagnosticSeverity } from "../../types/operation";

interface DiagnosticPanelProps {
  analysis: DiagnosticAnalysis;
  onRunCommand: (cmd: string) => void;
  onClose: () => void;
  onFollowUp: (message: string) => Promise<string>;
}

interface FollowUpMessage {
  role: "user" | "assistant";
  content: string;
}

const SEVERITY_CONFIG: Record<
  DiagnosticSeverity,
  { label: string; bg: string; text: string; border: string; icon: React.ReactNode }
> = {
  critical: {
    label: "Crítico",
    bg: "bg-red-950/40",
    text: "text-red-400",
    border: "border-red-800/60",
    icon: <AlertCircle size={14} className="text-red-400 shrink-0 mt-0.5" />,
  },
  high: {
    label: "Alto",
    bg: "bg-orange-950/40",
    text: "text-orange-400",
    border: "border-orange-800/60",
    icon: <AlertTriangle size={14} className="text-orange-400 shrink-0 mt-0.5" />,
  },
  medium: {
    label: "Médio",
    bg: "bg-yellow-950/30",
    text: "text-yellow-400",
    border: "border-yellow-800/60",
    icon: <AlertTriangle size={14} className="text-yellow-400 shrink-0 mt-0.5" />,
  },
  low: {
    label: "Baixo",
    bg: "bg-blue-950/30",
    text: "text-blue-400",
    border: "border-blue-800/60",
    icon: <Info size={14} className="text-blue-400 shrink-0 mt-0.5" />,
  },
  info: {
    label: "Info",
    bg: "bg-zinc-800/40",
    text: "text-zinc-400",
    border: "border-zinc-700/60",
    icon: <Info size={14} className="text-zinc-400 shrink-0 mt-0.5" />,
  },
};

export function DiagnosticPanel({
  analysis,
  onRunCommand,
  onClose,
  onFollowUp,
}: DiagnosticPanelProps) {
  const [expanded, setExpanded] = useState(true);
  const [followUpMessages, setFollowUpMessages] = useState<FollowUpMessage[]>([]);
  const [followUpInput, setFollowUpInput] = useState("");
  const [followUpLoading, setFollowUpLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [followUpMessages]);

  const handleFollowUp = async () => {
    const msg = followUpInput.trim();
    if (!msg || followUpLoading) return;
    setFollowUpInput("");
    const userMsg: FollowUpMessage = { role: "user", content: msg };
    setFollowUpMessages((prev) => [...prev, userMsg]);
    setFollowUpLoading(true);
    try {
      const reply = await onFollowUp(msg);
      setFollowUpMessages((prev) => [
        ...prev,
        { role: "assistant", content: reply },
      ]);
    } finally {
      setFollowUpLoading(false);
    }
  };

  const hasCritical = analysis.findings.some(
    (f) => f.severity === "critical" || f.severity === "high"
  );

  return (
    <div className="border border-zinc-700 rounded-lg bg-zinc-900 overflow-hidden mb-3">
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2.5 bg-zinc-800 cursor-pointer select-none"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-2">
          {hasCritical ? (
            <AlertTriangle size={15} className="text-orange-400" />
          ) : (
            <CheckCircle size={15} className="text-emerald-400" />
          )}
          <span className="text-sm font-semibold text-zinc-100">
            Análise de Diagnóstico
          </span>
          {analysis.requires_immediate_action && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-red-900/60 text-red-300 border border-red-700/50 font-medium">
              Ação imediata
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClose();
            }}
            className="p-1 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors"
            title="Fechar painel"
          >
            <X size={14} />
          </button>
          {expanded ? (
            <ChevronUp size={14} className="text-zinc-400" />
          ) : (
            <ChevronDown size={14} className="text-zinc-400" />
          )}
        </div>
      </div>

      {expanded && (
        <div className="p-4 space-y-4">
          {/* Summary */}
          <p className="text-sm text-zinc-300 leading-relaxed">{analysis.summary}</p>

          {/* Findings */}
          {analysis.findings.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                Achados ({analysis.findings.length})
              </h4>
              {analysis.findings.map((finding, i) => {
                const cfg = SEVERITY_CONFIG[finding.severity];
                return (
                  <div
                    key={i}
                    className={`rounded-md border p-3 ${cfg.bg} ${cfg.border}`}
                  >
                    <div className="flex items-start gap-2">
                      {cfg.icon}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className={`text-xs font-semibold ${cfg.text}`}>
                            {cfg.label}
                          </span>
                          <span className="text-xs font-medium text-zinc-200">
                            {finding.title}
                          </span>
                        </div>
                        <p className="text-xs text-zinc-400 leading-relaxed">
                          {finding.detail}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Root causes */}
          {analysis.root_causes.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                Causas raiz
              </h4>
              <ul className="space-y-1">
                {analysis.root_causes.map((cause, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-zinc-300">
                    <span className="text-zinc-600 mt-0.5">▸</span>
                    {cause}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommendations */}
          {analysis.recommendations.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                Recomendações
              </h4>
              <ul className="space-y-1">
                {analysis.recommendations.map((rec, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-zinc-300">
                    <CheckCircle size={11} className="text-emerald-500 shrink-0 mt-0.5" />
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Suggested follow-up commands */}
          {analysis.suggested_follow_up_commands.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
                <Terminal size={11} />
                Comandos sugeridos para aprofundar
              </h4>
              <div className="flex flex-wrap gap-2">
                {analysis.suggested_follow_up_commands.map((cmd, i) => (
                  <button
                    key={i}
                    onClick={() => onRunCommand(cmd)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-zinc-800 border border-zinc-700 hover:border-brand-500/60 hover:bg-zinc-750 transition-colors text-xs font-mono text-zinc-300 hover:text-zinc-100"
                    title={`Executar: ${cmd}`}
                  >
                    <Terminal size={10} className="text-zinc-500" />
                    {cmd}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Follow-up mini chat */}
          <div className="border-t border-zinc-800 pt-3 space-y-2">
            <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
              Perguntar sobre este diagnóstico
            </h4>

            {followUpMessages.length > 0 && (
              <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                {followUpMessages.map((m, i) => (
                  <div
                    key={i}
                    className={`text-xs rounded px-3 py-2 leading-relaxed ${
                      m.role === "user"
                        ? "bg-brand-600/20 text-zinc-200 border border-brand-600/30 ml-4"
                        : "bg-zinc-800 text-zinc-300 border border-zinc-700 mr-4"
                    }`}
                  >
                    {m.content}
                  </div>
                ))}
                {followUpLoading && (
                  <div className="flex items-center gap-2 text-xs text-zinc-500 ml-1">
                    <Loader2 size={11} className="animate-spin" />
                    Analisando…
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}

            <div className="flex gap-2">
              <input
                type="text"
                value={followUpInput}
                onChange={(e) => setFollowUpInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleFollowUp()}
                placeholder="Ex.: Qual a causa provável do problema de CPU?"
                disabled={followUpLoading}
                className="flex-1 text-xs bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-brand-500 disabled:opacity-50"
              />
              <button
                onClick={handleFollowUp}
                disabled={!followUpInput.trim() || followUpLoading}
                className="px-3 py-2 rounded bg-brand-600 hover:bg-brand-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                title="Enviar pergunta"
              >
                {followUpLoading ? (
                  <Loader2 size={13} className="animate-spin text-white" />
                ) : (
                  <Send size={13} className="text-white" />
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
