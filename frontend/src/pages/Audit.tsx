import { Fragment, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, XCircle, ChevronDown, ChevronRight, BookOpen, X, Loader2, Pencil } from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { StatusBadge } from "../components/shared/StatusBadge";
import { auditApi } from "../api/audit";
import { operationsApi } from "../api/operations";
import { AUDIT_INTENTS } from "../types/audit";

type Tab = "pending" | "direct" | "history";

const intentLabel = (key: string) => AUDIT_INTENTS.find((i) => i.key === key)?.label ?? key;
const fmtDate = (s: string | null) => (s ? new Date(s).toLocaleString("pt-BR") : "—");

// ── Pending Tab ───────────────────────────────────────────────────────────────
function PendingTab() {
  const qc = useQueryClient();
  const { data: ops = [], isLoading } = useQuery({
    queryKey: ["audit-pending"],
    queryFn: auditApi.getPending,
    refetchInterval: 30000,
  });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [comment, setComment] = useState("");

  const reviewMutation = useMutation({
    mutationFn: ({ id, approved, comment }: { id: string; approved: boolean; comment: string }) =>
      auditApi.review(id, { approved, comment }),
    onSuccess: (_data, vars) => {
      toast.success(vars.approved ? "Operação aprovada e executada!" : "Operação rejeitada.");
      setExpandedId(null);
      setComment("");
      qc.invalidateQueries({ queryKey: ["audit-pending"] });
      qc.invalidateQueries({ queryKey: ["audit-pending-count"] });
      qc.invalidateQueries({ queryKey: ["audit-history"] });
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Erro ao processar revisão.");
    },
  });

  if (isLoading) {
    return <div className="py-10 text-center text-gray-400">Carregando...</div>;
  }

  if (ops.length === 0) {
    return (
      <div className="py-14 text-center text-gray-400">
        <CheckCircle2 size={40} className="mx-auto mb-3 text-green-300" />
        <p className="text-sm">Nenhuma operação aguardando revisão.</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-gray-100">
      {ops.map((op) => (
        <Fragment key={op.id}>
          <button
            className="w-full text-left px-4 py-3 hover:bg-gray-50 flex items-start gap-3"
            onClick={() => {
              setExpandedId(expandedId === op.id ? null : op.id);
              setComment("");
            }}
          >
            <span className="mt-1 shrink-0 text-gray-400">
              {expandedId === op.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </span>
            <div className="flex-1 grid grid-cols-4 gap-4 items-center min-w-0">
              <div>
                <p className="text-sm font-medium text-gray-900 truncate">{op.requester_name ?? "—"}</p>
                <p className="text-xs text-gray-400 truncate">{op.requester_email}</p>
              </div>
              <div>
                <p className="text-sm text-gray-700 truncate">{op.device_name ?? "—"}</p>
                <p className="text-xs text-gray-400">{op.device_vendor}</p>
              </div>
              <div>
                <p className="text-sm text-gray-700">{op.intent ? intentLabel(op.intent) : "—"}</p>
              </div>
              <div className="text-right space-y-1">
                <StatusBadge status={op.status} />
                <p className="text-xs text-gray-400">{fmtDate(op.created_at)}</p>
              </div>
            </div>
          </button>

          {expandedId === op.id && (
            <div className="px-6 pb-5 bg-gray-50 border-t border-gray-100">
              <div className="pt-4 space-y-4 max-w-3xl">
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                    Solicitação Original
                  </p>
                  <p className="text-sm text-gray-800 bg-white border border-gray-200 rounded-lg p-3">
                    {op.natural_language_input}
                  </p>
                </div>

                {op.action_plan && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                      Plano de Ação
                    </p>
                    <pre className="text-xs text-gray-700 bg-white border border-gray-200 rounded-lg p-3 overflow-auto max-h-48 whitespace-pre-wrap">
                      {JSON.stringify(
                        Object.fromEntries(
                          Object.entries(op.action_plan).filter(([k]) => k !== "result")
                        ),
                        null,
                        2
                      )}
                    </pre>
                  </div>
                )}

                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                    Parecer do Revisor
                  </p>
                  <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="Comentário de revisão (obrigatório para rejeição)"
                    rows={3}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                  />
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => reviewMutation.mutate({ id: op.id, approved: true, comment })}
                    disabled={reviewMutation.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50"
                  >
                    <CheckCircle2 size={15} />
                    Aprovar e Executar
                  </button>
                  <button
                    onClick={() => {
                      if (!comment.trim()) {
                        toast.error("Informe o motivo da rejeição.");
                        return;
                      }
                      reviewMutation.mutate({ id: op.id, approved: false, comment });
                    }}
                    disabled={reviewMutation.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50"
                  >
                    <XCircle size={15} />
                    Rejeitar
                  </button>
                </div>
              </div>
            </div>
          )}
        </Fragment>
      ))}
    </div>
  );
}

// ── Direct Tab ────────────────────────────────────────────────────────────────
function DirectTab() {
  const { data: ops = [], isLoading } = useQuery({
    queryKey: ["audit-direct"],
    queryFn: auditApi.getDirect,
  });

  if (isLoading) return <div className="py-10 text-center text-gray-400">Carregando...</div>;
  if (ops.length === 0)
    return <div className="py-10 text-center text-gray-400 text-sm">Nenhuma operação registrada.</div>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100">
            {["Solicitante", "Dispositivo", "Intenção", "Status", "Data"].map((h) => (
              <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {ops.map((op) => (
            <tr key={op.id} className="hover:bg-gray-50">
              <td className="px-4 py-3">
                <p className="font-medium text-gray-900">{op.requester_name ?? "—"}</p>
                <p className="text-xs text-gray-400">{op.requester_email}</p>
              </td>
              <td className="px-4 py-3 text-gray-700">{op.device_name ?? "—"}</td>
              <td className="px-4 py-3 text-gray-700">{op.intent ? intentLabel(op.intent) : "—"}</td>
              <td className="px-4 py-3">
                <StatusBadge status={op.status} />
              </td>
              <td className="px-4 py-3 text-xs text-gray-400">{fmtDate(op.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Markdown renderer (no extra dependency) ────────────────────────────────
function inlineRender(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**"))
      return <strong key={i} className="font-semibold text-gray-900">{part.slice(2, -2)}</strong>;
    if (part.startsWith("*") && part.endsWith("*"))
      return <em key={i}>{part.slice(1, -1)}</em>;
    if (part.startsWith("`") && part.endsWith("`"))
      return <code key={i} className="bg-gray-100 px-1 rounded text-xs font-mono text-gray-800">{part.slice(1, -1)}</code>;
    return <span key={i}>{part}</span>;
  });
}

function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;
  let listItems: string[] = [];
  let listType: "ul" | "ol" | null = null;

  const flushList = (key: number) => {
    if (!listItems.length) return;
    const Tag = listType === "ul" ? "ul" : "ol";
    const cls = listType === "ul" ? "list-disc" : "list-decimal";
    elements.push(
      <Tag key={`list-${key}`} className={`${cls} ml-5 space-y-0.5 my-2`}>
        {listItems.map((item, idx) => (
          <li key={idx} className="text-sm text-gray-700">{inlineRender(item)}</li>
        ))}
      </Tag>
    );
    listItems = [];
    listType = null;
  };

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith("```")) {
      flushList(i);
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) { code.push(lines[i]); i++; }
      elements.push(
        <pre key={i} className="bg-gray-900 text-green-300 rounded-lg p-3 text-xs overflow-auto my-2 whitespace-pre-wrap">
          {code.join("\n")}
        </pre>
      );
    } else if (line.startsWith("### ")) {
      flushList(i);
      elements.push(<h3 key={i} className="text-sm font-bold text-gray-900 mt-4 mb-1">{inlineRender(line.slice(4))}</h3>);
    } else if (line.startsWith("## ")) {
      flushList(i);
      elements.push(<h2 key={i} className="text-base font-bold text-gray-800 mt-5 mb-2 border-b border-gray-200 pb-1">{inlineRender(line.slice(3))}</h2>);
    } else if (line.startsWith("# ")) {
      flushList(i);
      elements.push(<h1 key={i} className="text-lg font-bold text-gray-900 mt-4 mb-2">{inlineRender(line.slice(2))}</h1>);
    } else if (line.startsWith("> ")) {
      flushList(i);
      elements.push(
        <div key={i} className="bg-blue-50 border-l-4 border-blue-400 px-3 py-2 rounded text-sm text-blue-800 my-2">
          {inlineRender(line.slice(2))}
        </div>
      );
    } else if (line.match(/^[-*] /)) {
      if (listType !== "ul") { flushList(i); listType = "ul"; }
      listItems.push(line.slice(2));
    } else if (line.match(/^\d+\. /)) {
      if (listType !== "ol") { flushList(i); listType = "ol"; }
      listItems.push(line.replace(/^\d+\. /, ""));
    } else if (line.trim() === "") {
      flushList(i);
      elements.push(<div key={i} className="h-1" />);
    } else {
      flushList(i);
      elements.push(<p key={i} className="text-sm text-gray-700 leading-relaxed">{inlineRender(line)}</p>);
    }
    i++;
  }
  flushList(i);
  return elements;
}

// ── Tutorial Drawer ───────────────────────────────────────────────────────────
function TutorialDrawer({ operationId, onClose }: { operationId: string; onClose: () => void }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["tutorial", operationId],
    queryFn: () => operationsApi.getTutorial(operationId),
    staleTime: Infinity,
  });

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-white shadow-2xl flex flex-col h-full overflow-hidden animate-slide-in-right">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 shrink-0">
          <div className="flex items-center gap-2">
            <BookOpen size={18} className="text-brand-600" />
            <h2 className="text-base font-semibold text-gray-900">Tutorial Manual</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {isLoading && (
            <div className="flex flex-col items-center justify-center h-48 gap-3 text-gray-400">
              <Loader2 size={28} className="animate-spin" />
              <p className="text-sm">Gerando tutorial com IA...</p>
            </div>
          )}
          {isError && (
            <p className="text-sm text-red-500 text-center py-10">
              Erro ao gerar o tutorial. Tente novamente.
            </p>
          )}
          {data?.tutorial && (
            <div className="prose-sm max-w-none">
              {renderMarkdown(data.tutorial)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── History Tab ───────────────────────────────────────────────────────────────
function HistoryTab() {
  const navigate = useNavigate();
  const { data: ops = [], isLoading } = useQuery({
    queryKey: ["audit-history"],
    queryFn: auditApi.getHistory,
  });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [tutorialOpId, setTutorialOpId] = useState<string | null>(null);

  function editRoute(op: typeof ops[number]): string {
    const ap = op.action_plan as Record<string, unknown> | null;
    if (op.intent === "direct_ssh") {
      if (ap?.template_slug) return `/templates?edit=${op.id}`;
      return `/direct-mode?edit=${op.id}`;
    }
    return `/agent?edit=${op.id}`;
  }

  if (isLoading) return <div className="py-10 text-center text-gray-400">Carregando...</div>;
  if (ops.length === 0)
    return <div className="py-10 text-center text-gray-400 text-sm">Nenhuma operação no histórico.</div>;

  return (
    <>
      {tutorialOpId && (
        <TutorialDrawer operationId={tutorialOpId} onClose={() => setTutorialOpId(null)} />
      )}
    <div className="divide-y divide-gray-100">
      {ops.map((op) => (
        <Fragment key={op.id}>
          <button
            className="w-full text-left px-4 py-3 hover:bg-gray-50 flex items-start gap-3"
            onClick={() => setExpandedId(expandedId === op.id ? null : op.id)}
          >
            <span className="mt-1 shrink-0 text-gray-400">
              {expandedId === op.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </span>
            <div className="flex-1 grid grid-cols-5 gap-4 items-center min-w-0">
              <div>
                <p className="text-sm font-medium text-gray-900 truncate">{op.requester_name ?? "—"}</p>
                <p className="text-xs text-gray-400 truncate">{op.requester_email}</p>
              </div>
              <div>
                <p className="text-sm text-gray-700 truncate">{op.device_name ?? "—"}</p>
                <p className="text-xs text-gray-400">{op.device_vendor}</p>
              </div>
              <div>
                <p className="text-sm text-gray-700">{op.intent ? intentLabel(op.intent) : "—"}</p>
                <p className="text-xs text-gray-400">{op.reviewer_name ? `Revisor: ${op.reviewer_name}` : ""}</p>
              </div>
              <div>
                <StatusBadge status={op.status} />
              </div>
              <div className="text-right">
                <p className="text-xs text-gray-400">{fmtDate(op.reviewed_at ?? op.created_at)}</p>
              </div>
            </div>
          </button>

          {expandedId === op.id && (
            <div className="px-6 pb-5 bg-gray-50 border-t border-gray-100">
              <div className="pt-4 space-y-4 max-w-3xl">
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                    Solicitação Original
                  </p>
                  <p className="text-sm text-gray-800 bg-white border border-gray-200 rounded-lg p-3">
                    {op.natural_language_input}
                  </p>
                </div>

                {op.action_plan && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                      Plano de Ação
                    </p>
                    <pre className="text-xs text-gray-700 bg-white border border-gray-200 rounded-lg p-3 overflow-auto max-h-64 whitespace-pre-wrap">
                      {JSON.stringify(
                        Object.fromEntries(
                          Object.entries(op.action_plan).filter(([k]) => k !== "result")
                        ),
                        null,
                        2
                      )}
                    </pre>
                  </div>
                )}

                {(() => {
                  const result = op.action_plan?.result as Record<string, unknown> | undefined;
                  const sshOutput = result?.output as string | undefined;
                  const sshCmds = result?.commands as string[] | undefined;
                  if (!sshOutput && !sshCmds) return null;
                  return (
                    <div>
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                        Output SSH do Dispositivo
                      </p>
                      {sshCmds && sshCmds.length > 0 && (
                        <p className="text-xs text-gray-500 mb-1">
                          Comandos enviados: <code className="bg-gray-100 px-1 rounded">{sshCmds.join(" → ")}</code>
                        </p>
                      )}
                      <pre className={`text-xs rounded-lg p-3 overflow-auto max-h-64 whitespace-pre-wrap border ${
                        op.status === "failed"
                          ? "bg-red-50 border-red-200 text-red-800"
                          : "bg-gray-900 border-gray-700 text-green-300"
                      }`}>
                        {sshOutput ?? "(sem output)"}
                      </pre>
                    </div>
                  );
                })()}

                {op.review_comment && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                      Parecer do Revisor
                      {op.reviewer_name && (
                        <span className="ml-2 font-normal normal-case text-gray-400">
                          — {op.reviewer_name} em {fmtDate(op.reviewed_at)}
                        </span>
                      )}
                    </p>
                    <p className="text-sm text-gray-800 bg-white border border-gray-200 rounded-lg p-3">
                      {op.review_comment}
                    </p>
                  </div>
                )}

                <div className="pt-1 flex flex-wrap gap-2">
                  {op.status === "completed" && (
                    <button
                      onClick={(e) => { e.stopPropagation(); setTutorialOpId(op.id); }}
                      className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-brand-600 border border-brand-300 rounded-lg hover:bg-brand-50 transition-colors"
                    >
                      <BookOpen size={15} />
                      Ver como fazer manualmente
                    </button>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); navigate(editRoute(op)); }}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    <Pencil size={15} />
                    Editar / Repetir
                  </button>
                </div>
              </div>
            </div>
          )}
        </Fragment>
      ))}
    </div>
    </>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function Audit() {
  const [tab, setTab] = useState<Tab>("pending");

  const { data: pendingCount = 0 } = useQuery({
    queryKey: ["audit-pending-count"],
    queryFn: auditApi.getPendingCount,
    refetchInterval: 30000,
  });

  const tabs: { id: Tab; label: string }[] = [
    { id: "pending", label: pendingCount > 0 ? `Pendentes (${pendingCount})` : "Pendentes" },
    { id: "direct", label: "Realizadas" },
    { id: "history", label: "Histórico" },
  ];

  return (
    <PageWrapper title="Auditoria">
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex border-b border-gray-200 px-2 pt-2">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px mr-1 ${
                tab === t.id
                  ? "border-brand-600 text-brand-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "pending" && <PendingTab />}
        {tab === "direct" && <DirectTab />}
        {tab === "history" && <HistoryTab />}
      </div>
    </PageWrapper>
  );
}
