import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock,
  ExternalLink,
  Loader2,
  MessageSquare,
  RefreshCw,
  RotateCcw,
  Shield,
  X,
  XCircle,
} from "lucide-react";
import toast from "react-hot-toast";
import { PageWrapper } from "../components/layout/PageWrapper";
import { glpiApi } from "../api/glpi";
import type { GlpiAnalysisStatus, GlpiAnalysisListItem, GlpiTicketAnalysis } from "../types/glpi";

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<GlpiAnalysisStatus, string> = {
  pending:   "Pendente",
  analyzing: "Analisando",
  completed: "Concluído",
  failed:    "Falhou",
};

const STATUS_STYLE: Record<GlpiAnalysisStatus, string> = {
  pending:   "bg-gray-100 text-gray-600",
  analyzing: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed:    "bg-red-100 text-red-700",
};

const ITEMTYPE_LABEL: Record<string, string> = {
  Ticket:  "Ticket",
  Problem: "Problema",
  Change:  "Mudança",
};

const ITEMTYPE_STYLE: Record<string, string> = {
  Ticket:  "bg-blue-50 text-blue-700",
  Problem: "bg-red-50 text-red-700",
  Change:  "bg-purple-50 text-purple-700",
};

function glpiItemUrl(baseUrl: string, itemtype: string, id: number): string {
  const paths: Record<string, string> = {
    Ticket:  "ticket",
    Problem: "problem",
    Change:  "change",
  };
  return `${baseUrl}/front/${paths[itemtype] ?? "ticket"}.form.php?id=${id}`;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function ConfidenceBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-gray-300">—</span>;
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? "text-green-600" : pct >= 60 ? "text-yellow-600" : "text-red-500";
  return <span className={`font-medium ${color}`}>{pct}%</span>;
}

// ── Detail slide-over ─────────────────────────────────────────────────────────

function AnalysisSlideOver({
  analysisId,
  onClose,
}: {
  analysisId: string;
  onClose: () => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["glpi-analysis", analysisId],
    queryFn: () => glpiApi.getAnalysis(analysisId),
  });

  function Section({ title, content }: { title: string; content: string | null }) {
    if (!content) return null;
    return (
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{title}</p>
        <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{content}</p>
      </div>
    );
  }

  const glpiLink = data?.glpi_url
    ? glpiItemUrl(data.glpi_url, data.glpi_itemtype, data.glpi_ticket_id)
    : null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-white shadow-2xl flex flex-col h-full overflow-hidden animate-slide-in-right">
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-gray-200 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <MessageSquare size={18} className="text-brand-600 shrink-0" />
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-xs text-gray-400">#{data?.glpi_ticket_id}</p>
                {data?.glpi_itemtype && (
                  <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${ITEMTYPE_STYLE[data.glpi_itemtype] ?? "bg-gray-100 text-gray-600"}`}>
                    {ITEMTYPE_LABEL[data.glpi_itemtype] ?? data.glpi_itemtype}
                  </span>
                )}
              </div>
              <h2 className="text-sm font-semibold text-gray-900 truncate">
                {data?.glpi_ticket_title ?? "Carregando..."}
              </h2>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 ml-3">
            {glpiLink && (
              <a
                href={glpiLink}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium"
                title="Abrir no GLPI"
              >
                <ExternalLink size={13} />
                GLPI
              </a>
            )}
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {isLoading && (
            <div className="flex items-center justify-center h-48 text-gray-400 gap-2">
              <Loader2 size={20} className="animate-spin" />
              <span className="text-sm">Carregando análise...</span>
            </div>
          )}

          {data && (
            <div className="space-y-5">
              {/* Badges row */}
              <div className="flex flex-wrap gap-2">
                <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${STATUS_STYLE[data.status]}`}>
                  {STATUS_LABEL[data.status]}
                </span>
                {data.is_security_incident && (
                  <span className="flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-red-100 text-red-700">
                    <AlertTriangle size={11} /> Incidente de segurança
                  </span>
                )}
                {data.is_recurrent && (
                  <span className="flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-amber-100 text-amber-700">
                    <RotateCcw size={11} /> Recorrente ({data.recurrence_count}x)
                  </span>
                )}
                {data.confianca !== null && (
                  <span className="flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-gray-100 text-gray-600">
                    Confiança: {Math.round(data.confianca * 100)}%
                  </span>
                )}
              </div>

              {/* Analysis sections */}
              {data.status === "completed" ? (
                <div className="space-y-5 divide-y divide-gray-100">
                  <Section title="Diagnóstico"           content={data.diagnostico} />
                  <div className="pt-5"><Section title="Ações imediatas"    content={data.acoes_imediatas} /></div>
                  <div className="pt-5"><Section title="Causa raiz"         content={data.causa_raiz} /></div>
                  <div className="pt-5"><Section title="Plano de remediação" content={data.plano_remediacao} /></div>
                  <div className="pt-5"><Section title="Prevenção"          content={data.prevencao} /></div>
                </div>
              ) : data.status === "failed" ? (
                <div className="bg-red-50 border border-red-100 rounded-lg px-4 py-3 text-sm text-red-700">
                  <p className="font-medium mb-1">Falha na análise</p>
                  <p className="text-xs text-red-500">{data.error_message ?? "Erro desconhecido"}</p>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-sm text-gray-400 py-8 justify-center">
                  <Loader2 size={16} className="animate-spin" />
                  Análise em andamento...
                </div>
              )}

              {/* Ticket content */}
              {data.glpi_ticket_content && (
                <div className="pt-2 border-t border-gray-100">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Descrição original</p>
                  <p className="text-xs text-gray-500 whitespace-pre-wrap leading-relaxed bg-gray-50 rounded-lg p-3">
                    {data.glpi_ticket_content}
                  </p>
                </div>
              )}

              {/* Meta */}
              <div className="flex items-center gap-3 text-xs text-gray-400 pt-2 border-t border-gray-100 flex-wrap">
                <span>Analisado em {fmtDate(data.created_at)}</span>
                {data.glpi_followup_id && (
                  glpiLink ? (
                    <a
                      href={glpiLink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-green-600 hover:text-green-700 font-medium"
                    >
                      <CheckCircle2 size={11} />
                      Nota postada no GLPI (#{data.glpi_followup_id})
                      <ExternalLink size={10} />
                    </a>
                  ) : (
                    <span className="text-green-600">✓ Nota postada no GLPI (#{data.glpi_followup_id})</span>
                  )
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Filter pill ───────────────────────────────────────────────────────────────

function FilterPill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border transition-colors ${
        active
          ? "bg-brand-600 text-white border-brand-600"
          : "bg-white text-gray-600 border-gray-200 hover:border-brand-400 hover:text-brand-600"
      }`}
    >
      {children}
    </button>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function GlpiAnalyses() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter]   = useState<GlpiAnalysisStatus | "">("");
  const [itemtypeFilter, setItemtypeFilter] = useState<string>("");
  const [securityOnly, setSecurityOnly]   = useState(false);
  const [recurrentOnly, setRecurrentOnly] = useState(false);
  const [selectedId, setSelectedId]       = useState<string | null>(null);

  const { data: integration } = useQuery({
    queryKey: ["glpi-integration"],
    queryFn: glpiApi.getIntegration,
  });

  const { data: analyses = [], isLoading, refetch } = useQuery({
    queryKey: ["glpi-analyses", statusFilter, itemtypeFilter, securityOnly, recurrentOnly],
    queryFn: () =>
      glpiApi.listAnalyses({
        status:         statusFilter || undefined,
        itemtype:       itemtypeFilter || undefined,
        security_only:  securityOnly || undefined,
        recurrent_only: recurrentOnly || undefined,
        limit: 200,
      }),
  });

  const syncMut = useMutation({
    mutationFn: () => glpiApi.triggerSync(integration!.id),
    onSuccess: () => {
      toast.success("Sincronização iniciada. Análises aparecerão em instantes.");
      setTimeout(() => refetch(), 5000);
    },
    onError: () => toast.error("Falha ao iniciar sincronização"),
  });

  const securityCount  = analyses.filter((a) => a.is_security_incident).length;
  const recurrentCount = analyses.filter((a) => a.is_recurrent).length;

  // Count by itemtype for badges
  const countByType = analyses.reduce<Record<string, number>>((acc, a) => {
    acc[a.glpi_itemtype] = (acc[a.glpi_itemtype] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <PageWrapper title="Tickets IA">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900">Tickets IA</h1>
          {analyses.length > 0 && (
            <span className="text-xs bg-gray-100 text-gray-600 px-2.5 py-0.5 rounded-full font-medium">
              {analyses.length} {analyses.length === 1 ? "item" : "itens"}
            </span>
          )}
        </div>
        <button
          onClick={() => syncMut.mutate()}
          disabled={syncMut.isPending || !integration?.is_active}
          title={!integration ? "Nenhuma integração GLPI configurada" : undefined}
          className="flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw size={14} className={syncMut.isPending ? "animate-spin" : ""} />
          {syncMut.isPending ? "Sincronizando..." : "Sync agora"}
        </button>
      </div>

      {/* No integration configured */}
      {!integration && !isLoading && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-4 text-sm text-amber-800 mb-5">
          Nenhuma integração GLPI configurada. Acesse{" "}
          <a href="/organization" className="font-semibold underline hover:text-amber-900">
            Organização → Integrações
          </a>{" "}
          para configurar.
        </div>
      )}

      {/* Status filters */}
      <div className="flex flex-wrap gap-2 mb-2">
        <FilterPill active={statusFilter === ""} onClick={() => setStatusFilter("")}>
          Todos
        </FilterPill>
        <FilterPill active={statusFilter === "completed"} onClick={() => setStatusFilter(statusFilter === "completed" ? "" : "completed")}>
          <CheckCircle2 size={11} /> Concluídos
        </FilterPill>
        <FilterPill active={statusFilter === "analyzing"} onClick={() => setStatusFilter(statusFilter === "analyzing" ? "" : "analyzing")}>
          <Clock size={11} /> Analisando
        </FilterPill>
        <FilterPill active={statusFilter === "failed"} onClick={() => setStatusFilter(statusFilter === "failed" ? "" : "failed")}>
          <XCircle size={11} /> Falhou
        </FilterPill>
        <FilterPill active={securityOnly} onClick={() => setSecurityOnly((v) => !v)}>
          <AlertTriangle size={11} />
          Segurança {securityCount > 0 && <span className="bg-red-500 text-white rounded-full px-1 text-[10px]">{securityCount}</span>}
        </FilterPill>
        <FilterPill active={recurrentOnly} onClick={() => setRecurrentOnly((v) => !v)}>
          <RotateCcw size={11} />
          Recorrentes {recurrentCount > 0 && <span className="bg-amber-500 text-white rounded-full px-1 text-[10px]">{recurrentCount}</span>}
        </FilterPill>
      </div>

      {/* Type filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        <FilterPill active={itemtypeFilter === ""} onClick={() => setItemtypeFilter("")}>
          Todos os tipos
        </FilterPill>
        {(["Ticket", "Problem", "Change"] as const).map((t) => (
          <FilterPill
            key={t}
            active={itemtypeFilter === t}
            onClick={() => setItemtypeFilter(itemtypeFilter === t ? "" : t)}
          >
            {ITEMTYPE_LABEL[t]}
            {countByType[t] != null && (
              <span className="bg-white/30 text-current rounded-full px-1 text-[10px] font-bold">
                {countByType[t]}
              </span>
            )}
          </FilterPill>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-48 gap-2 text-gray-400">
            <Loader2 size={20} className="animate-spin" />
            <span className="text-sm">Carregando análises...</span>
          </div>
        ) : analyses.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-2 text-gray-400">
            <MessageSquare size={32} className="opacity-30" />
            <p className="text-sm">Nenhuma análise encontrada</p>
            {integration && (
              <p className="text-xs text-gray-300">
                O worker processa novos itens a cada {integration.poll_interval_minutes} minutos
              </p>
            )}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-16">#</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-24">Tipo</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Título</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-28">Status</th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-16">Seg.</th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-24">Recorrente</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-20">Conf.</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-36">Data</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {analyses.map((a) => (
                <tr
                  key={a.id}
                  onClick={() => setSelectedId(a.id)}
                  className="hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 text-gray-400 font-mono text-xs">{a.glpi_ticket_id}</td>
                  <td className="px-4 py-3">
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${ITEMTYPE_STYLE[a.glpi_itemtype] ?? "bg-gray-100 text-gray-600"}`}>
                      {ITEMTYPE_LABEL[a.glpi_itemtype] ?? a.glpi_itemtype}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-gray-800 font-medium truncate max-w-xs">{a.glpi_ticket_title || "—"}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLE[a.status]}`}>
                      {STATUS_LABEL[a.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {a.is_security_incident
                      ? <AlertTriangle size={14} className="text-red-500 mx-auto" />
                      : <span className="text-gray-200">—</span>}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {a.is_recurrent
                      ? <span className="flex items-center justify-center gap-1 text-xs text-amber-600"><RotateCcw size={11} />{a.recurrence_count}x</span>
                      : <span className="text-gray-200">—</span>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ConfidenceBadge value={a.confianca} />
                  </td>
                  <td className="px-4 py-3 text-right text-xs text-gray-400 whitespace-nowrap">
                    {fmtDate(a.created_at)}
                  </td>
                  <td className="px-3 py-3">
                    <ChevronRight size={14} className="text-gray-300" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Slide-over detail */}
      {selectedId && (
        <AnalysisSlideOver analysisId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </PageWrapper>
  );
}
